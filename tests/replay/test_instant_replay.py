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

from glitchygames.audio.live import VoiceState
from glitchygames.audio.synth import Waveform
from glitchygames.effects.shake import Shake, ShakeStyle, ShakeTarget
from glitchygames.events import FPSEVENT
from glitchygames.input import devices as devices_module
from glitchygames.input.state import IDLE_INPUT, current_input
from glitchygames.instant_replay import (
    JOURNAL_BYTES_PER_MINUTE_LIMIT,
    JOURNAL_START_FRAME,
    InstantReplayJournal,
    JournalRecording,
)
from glitchygames.live_sources import LiveSources
from glitchygames.recording import (
    EXTERNAL_ORIGIN,
    INTERNAL_ORIGIN,
    PLAYBACK_ANSWERS_FIELD,
    REDELIVERED_EVENTS_FIELD,
    RESUME_BRIDGE_FIELD,
    SAVES_OPENED_FIELD,
    SCENE_START_FIELD,
    post_event,
    post_input_event,
)
from glitchygames.replay.driver import ReplaySources
from glitchygames.replay.ghosts import GhostRecorder
from glitchygames.replay.playback import (
    INSTANT_PLAYBACK,
    PlaybackOptions,
    fast_forward_frame_count,
    start_playback,
    start_playback_from_recording,
)
from glitchygames.replay.silence import FrameSilencer
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.sources import active_sources
from glitchygames.state import open_saves
from glitchygames.state.manager import DiskSaveManager
from glitchygames.supervision import BREAKPOINT_KIND
from glitchygames.tracing import read_trace_result, write_trace
from tests.replay.playback_fixtures import (
    COUNTING_SAVE_NAMESPACE,
    COUNTING_SAVE_SLOT,
    CountingScene,
    InputReadingScene,
    KeyReleaseCountingScene,
    PostingCountingScene,
    SavingCountingScene,
    active_counting_scene,
    record_counting_scene,
    step_finishing,
)
from tests.replay.test_playback_scope import LivePostingSupervisor
from tests.world.test_frame_integration import CameraFreeScene, running_scene, step

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from pytest_mock import MockerFixture

    from glitchygames.events.base import HashableEvent
    from glitchygames.replay.playback import PlaybackOutcome, PlaybackSources

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
# How far a granted instant replay moves InstantSelfReplayingScene's marker (a refusal: 1)
SELF_REPLAY_GRANTED_STEP = 3
# InstantJoystickScene opens its second joystick on this tick
JOYSTICK_OPENING_TICK = 3
FAKE_JOYSTICK_COUNT = 2
FAKE_INSTANCE_IDS = (5, 6)
SETUP_SAVE_NAMESPACE = 'setup-saves'
SETUP_SAVED_VALUE = 7
# Paused frames beyond the fast-forward budget (PAUSE_BUDGET_FRAMES of frame time)
PAUSE_BUDGET_FRAMES = 10
# A goal's shake, still running when the instant replay starts, and a later WORLD shake
GOAL_SHAKE = Shake(style=ShakeStyle.JITTER, strength=8.0, duration=1.0, frequency=30.0)
LATER_WORLD_SHAKE = Shake(style=ShakeStyle.JITTER, strength=8.0, duration=0.2, frequency=30.0)
# An instant replay of INSTANT_LIVE_FRAMES live frames that shows the last SHOWN_FRAMES of them
INSTANT_LIVE_FRAMES = 30
SHOWN_FRAMES = 10
MATCHED_LIVE_FRAMES = 20
# A budget the live frames are past
REFUSING_BUDGET_FRAMES = 5
# InstantGoalScene asks for an instant replay on this tick; a later one shows this many frames
GOAL_TICK = 6
SHOWN_FRAMES_AFTER_GOAL = 3
# A fast-forwarding scope ends its silence after its last fast-forwarded frame and as it ends
FINISHES_PER_FAST_FORWARDING_SCOPE = 2


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


class SwitchingToInstantPostingScene(CountingScene):
    """Switches to an InstantPostingScene (it posts in its first dt_tick) on SWITCH_FRAME."""

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Request the posting instant-replay scene on SWITCH_FRAME."""
        super().dt_tick(dt)
        if self.frames_ticked == SWITCH_FRAME:
            self.next_scene = InstantPostingScene(options=self.options)


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


class InstantSelfReplayingScene(KeyReleaseCountingScene):
    """Shows its own instant replay on R, as a game shows one after every goal.

    What the request answered moves its marker (so a different answer in a playback of its
    journal diverges). Asks the recorded answer first, as ``SceneManager.instant_replay`` does:
    inside a playback of its journal the rebuilt scene keeps no journal of its own.
    """

    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = INSTANT_REPLAY_TEST_SECONDS

    @override
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Ask for an instant replay of this scene on R."""
        if event.key != pygame.K_r:
            super().on_key_down_event(event)
            return
        manager = SceneManager()
        granted = manager.recorded_playback_answer()
        if granted is None:
            journal = manager.instant_replay_journal
            assert journal is not None
            recording = journal.as_recording()
            granted = start_playback(
                manager=manager,
                header=recording.header,
                frames=recording.frames,
                then=self,
                options=PlaybackOptions(kind=INSTANT_PLAYBACK, start_frame=recording.start_frame),
            )
        self.marker.rect.y += SELF_REPLAY_GRANTED_STEP if granted else 1


class InstantGoalScene(KeyReleaseCountingScene):
    """Shows an instant replay of itself after its goal (on GOAL_TICK), as a game does; R too.

    Both go through ``SceneManager.instant_replay``; what each answered moves the marker (so a
    different answer in a playback of its journal diverges).
    """

    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = INSTANT_REPLAY_TEST_SECONDS

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Ask for an instant replay on GOAL_TICK."""
        super().dt_tick(dt)
        if self.frames_ticked == GOAL_TICK:
            self._show_instant_replay()

    @override
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Ask for an instant replay on R."""
        if event.key == pygame.K_r:
            self._show_instant_replay()
            return
        super().on_key_down_event(event)

    def _show_instant_replay(self: Self) -> None:
        """Ask for the instant replay; its answer moves the marker."""
        granted = SceneManager().instant_replay()
        self.marker.rect.y += SELF_REPLAY_GRANTED_STEP if granted else 1


class InstantEndingScene(InstantKeyReleaseScene):
    """Asks to end any playback on E, from its own key handler (scene code, not a supervisor)."""

    @override
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Ask to end the playback on E."""
        if event.key == pygame.K_e:
            SceneManager().end_playback()
            return
        super().on_key_down_event(event)


class InstantShakingScene(InstantSelfReplayingScene):
    """Shakes on S (a long JITTER shake of the world and the screen) and W (a short WORLD one).

    Its world sprite is drawn shaken, so a shake that draws differently from the shared shake
    stream diverges.
    """

    @override
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Start the long shake on S, the short WORLD shake on W."""
        if event.key == pygame.K_s:
            self.shake(GOAL_SHAKE, targets=ShakeTarget.WORLD | ShakeTarget.SCREEN)
        elif event.key == pygame.K_w:
            self.shake(LATER_WORLD_SHAKE, targets=ShakeTarget.WORLD)
        else:
            super().on_key_down_event(event)


class InstantJoystickScene(CountingScene):
    """Counts and opens joysticks as it is built and again on a tick; their answers move it."""

    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = INSTANT_REPLAY_TEST_SECONDS

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Count the joysticks and open the first, through the devices door.

        Args:
            options: The game's options.
            groups: The sprite group.

        """
        super().__init__(options=options, groups=groups)
        registry = active_sources().devices()
        self.joystick_count_seen = registry.joystick_count()
        self.joysticks: list[Any] = [registry.open_joystick(device_index=0)]

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Open the second joystick on its tick; place the marker by the answers and an axis."""
        super().dt_tick(dt)
        if self.frames_ticked == JOYSTICK_OPENING_TICK:
            registry = active_sources().devices()
            self.joystick_count_seen += registry.joystick_count()
            self.joysticks.append(registry.open_joystick(device_index=1))
        self.marker.rect.y = (
            self.joystick_count_seen * 10
            + sum(joystick.get_instance_id() for joystick in self.joysticks)
            # Polled through the frame's snapshot, never from the device itself
            + round(
                current_input().axis(device_id=self.joysticks[0].get_instance_id(), axis=0) * 10
            )
        )


class GhostRecordingScene(InstantCountingScene):
    """Records a ghost of its world sprite from every setup(), as a time-trial scene does."""

    # Every recorder made, in order (the live scene's, then a rebuilt scene's)
    recorders: ClassVar[list[GhostRecorder]] = []

    @override
    def setup(self: Self) -> None:
        """Start recording this scene's world sprite."""
        super().setup()
        GhostRecordingScene.recorders.append(GhostRecorder(sprite=self.world_sprite, scene=self))


class FrameCountingSupervisor:
    """Counts the frames it is called in."""

    def __init__(self: Self) -> None:
        """Start at no frames."""
        self.frames_seen = 0

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Count the frame (implements glitchygames.supervision.Supervisor)."""
        del frame_number, scene
        self.frames_seen += 1


class SupervisorAddingSupervisor:
    """A live supervisor that adds another supervisor on its Nth call (during a scope)."""

    def __init__(self: Self, *, on_call: int, added: FrameCountingSupervisor) -> None:
        """Add ``added`` on call number ``on_call``.

        Args:
            on_call: The call (1 = the first) that adds it.
            added: The supervisor to add.

        """
        self._calls = 0
        self._on_call = on_call
        self._added = added

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Add the supervisor on the chosen call (implements Supervisor)."""
        del frame_number, scene
        self._calls += 1
        if self._calls == self._on_call:
            SceneManager().add_supervisor(supervisor=self._added)


class InputPostingSupervisor:
    """Posts one user event as input (``post_input_event``) on its Nth call outside a scope."""

    def __init__(self: Self, *, on_call: int) -> None:
        """Post on call number ``on_call``.

        Args:
            on_call: The call (1 = the first) that posts.

        """
        self._calls = 0
        self._on_call = on_call
        self.posts = 0

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Post on the chosen call (implements Supervisor)."""
        del frame_number, scene
        if SceneManager().playback_session is not None:
            return
        self._calls += 1
        if self._calls == self._on_call:
            self.posts += 1
            post_input_event(pygame.event.Event(pygame.USEREVENT, {'input_from_supervisor': 1}))


class ScopeInputPostingSupervisor:
    """Posts one user event as input on its Nth call, live or in a scope (a scene's own)."""

    def __init__(self: Self, *, on_call: int) -> None:
        """Post on call number ``on_call``.

        Args:
            on_call: The call (1 = the first) that posts.

        """
        self._calls = 0
        self._on_call = on_call

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Post on the chosen call (implements Supervisor)."""
        del frame_number, scene
        self._calls += 1
        if self._calls == self._on_call:
            InputSupervisingScene.posts_by_supervisors += 1
            post_input_event(pygame.event.Event(pygame.USEREVENT, {'input_from_supervisor': 1}))


class GoalInUpdateScene(KeyReleaseCountingScene):
    """Posts its goal in update() (after the frame's pump); the goal asks for an instant replay.

    Every request is kept with whether a scope played it and what it got.
    """

    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = INSTANT_REPLAY_TEST_SECONDS
    # (asked inside a playback scope, granted) for every request, in order
    requests: ClassVar[list[tuple[bool, bool]]] = []

    @override
    def update(self: Self) -> None:
        """Post the goal on GOAL_TICK."""
        super().update()
        if self.frames_ticked == GOAL_TICK:
            post_event(pygame.event.Event(pygame.USEREVENT, {'goal': True}))

    @override
    def on_user_event(self: Self, event: HashableEvent) -> None:
        """Ask for an instant replay of the goal."""
        if getattr(event, 'goal', False):
            manager = SceneManager()
            granted = manager.instant_replay()
            GoalInUpdateScene.requests.append((manager.playback_session is not None, granted))


class GoalInUpdatePostingScene(GoalInUpdateScene, PostingCountingScene):
    """A goal scene that also posts an internal event every tick (matched in a playback)."""


class InstantUserEventScene(InstantCountingScene):
    """Moves its marker for every user event it is handed (a lost or extra one diverges)."""

    @override
    def on_user_event(self: Self, event: HashableEvent) -> None:
        """Move the marker down a pixel."""
        super().on_user_event(event)
        self.marker.rect.y += 1


class InputSupervisingScene(InstantUserEventScene):
    """Adds a supervisor that posts input in every setup() (a rebuilt scene's too)."""

    posts_by_supervisors: ClassVar[int] = 0

    @override
    def setup(self: Self) -> None:
        """Add the posting supervisor, as the played scene will again."""
        super().setup()
        SceneManager().add_supervisor(supervisor=ScopeInputPostingSupervisor(on_call=2))


class HandlerAddingScene(InstantCountingScene):
    """Adds a breakpoint handler in every setup() (a rebuilt scene's too)."""

    # Every breakpoint any of their handlers saw, by scene
    breakpoints_seen: ClassVar[list[object]] = []

    @override
    def setup(self: Self) -> None:
        """Add a handler noting the breakpoints this scene sees."""
        super().setup()
        SceneManager().add_control_event_handler(
            kind=BREAKPOINT_KIND,
            handler=lambda control_event: HandlerAddingScene.breakpoints_seen.append(self),
        )


class CleanupSupervisingScene(CountingScene):
    """Adds a supervisor in its cleanup() (as a scene handing over to the next might)."""

    added_in_cleanup: ClassVar[list[FrameCountingSupervisor]] = []

    @override
    def cleanup(self: Self) -> None:
        """Add a supervisor."""
        super().cleanup()
        supervisor = FrameCountingSupervisor()
        CleanupSupervisingScene.added_in_cleanup.append(supervisor)
        SceneManager().add_supervisor(supervisor=supervisor)


class SetupSavesScene(CountingScene):
    """Opens its save store in setup() and places its marker by the saved value."""

    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = INSTANT_REPLAY_TEST_SECONDS

    @override
    def setup(self: Self) -> None:
        """Read the saved value (the store's first opening in the run)."""
        super().setup()
        loaded = open_saves(app_name=SETUP_SAVE_NAMESPACE).load(COUNTING_SAVE_SLOT)
        self.saved_value = int(loaded['value'])

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Place the marker by the saved value."""
        super().dt_tick(dt)
        self.marker.rect.y = self.saved_value


class PostingInUpdateScene(CountingScene):
    """Posts a custom event in its render phase and leaves for the opted-in scene on a tick.

    The post is queued for the next frame, the opted-in scene's first logic frame: it was
    posted before that scene was even set up.
    """

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Leave for the instant-replay scene on SWITCH_FRAME."""
        super().dt_tick(dt)
        if self.frames_ticked == SWITCH_FRAME:
            self.next_scene = InstantCountingScene(options=self.options)

    @override
    def update(self: Self) -> None:
        """Post the leaving tick's event in the render phase."""
        super().update()
        if self.frames_ticked == SWITCH_FRAME:
            post_event(pygame.event.Event(pygame.USEREVENT, {'farewell': True}))


def journal_of(manager: SceneManager) -> InstantReplayJournal:
    """Return the scene manager's journal, checked to exist.

    Returns:
        The journal.

    """
    journal = manager.instant_replay_journal
    assert journal is not None
    return journal


def play_journal(
    *,
    manager: SceneManager,
    recording: JournalRecording,
    then: Scene,
    stepper: Callable[..., None] = step,
) -> None:
    """Play a journal's recording in a playback scope until it ends, and check it matched.

    Args:
        manager: The running scene manager (stepped by the golden harness).
        recording: The journal's recording.
        then: The scene to return to.
        stepper: How frames are run (``step``, or ``step_finishing`` for the frame clock).

    """
    assert start_playback(
        manager=manager,
        header=recording.header,
        frames=recording.frames,
        then=then,
        options=PlaybackOptions(kind=INSTANT_PLAYBACK, start_frame=recording.start_frame),
    )
    stepper(manager, frames=len(recording.frames) - recording.start_frame)
    assert manager.playback_session is None
    result = manager.last_playback_result
    assert result is not None
    assert result.divergence is None, result.report()
    assert result.end_reason == 'end_of_recording'
    assert manager.active_scene is then


def step_until_the_scope_ends(*, manager: SceneManager, stepper: Callable[..., None]) -> None:
    """Run frames while a playback scope plays.

    Args:
        manager: The running scene manager.
        stepper: How frames are run (``step`` or ``step_finishing``).

    """
    while manager.playback_session is not None:
        stepper(manager)


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

    def test_a_save_store_first_opened_in_setup_plays_back(self):
        """setup() opens it after the start is complete: the lead-in frame holds its snapshot."""
        with running_scene(CameraFreeScene) as manager:
            # Written behind the doors' back, so the run first opens the store in setup()
            DiskSaveManager(app_name=SETUP_SAVE_NAMESPACE).save(
                COUNTING_SAVE_SLOT, {'value': SETUP_SAVED_VALUE}
            )
            manager.switch_to_scene(SetupSavesScene(options=manager.OPTIONS))
            step(manager, frames=JOURNALED_FRAMES)
            live_scene = active_counting_scene(manager)
            recording = journal_of(manager).as_recording()
            assert SETUP_SAVE_NAMESPACE in recording.frames[0][SAVES_OPENED_FIELD]
            play_journal(manager=manager, recording=recording, then=live_scene)

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

    def test_the_paused_games_voice_survives_an_instant_replay_from_the_pause_screen(self):
        """The paused game waits behind the scope too, when its playback switches scenes."""
        with running_scene(InstantCountingScene) as manager:
            live_scene = active_counting_scene(manager)
            voice = manager.live_audio.create_voice(
                owner=live_scene, waveform=Waveform.SAWTOOTH, frequency=220.0, volume=0.1
            )
            voice.start()
            step(manager, frames=2)
            # A paused and resumed stretch: the playback switches to its pause screen and back
            step(manager, press(pygame.K_p))
            step(manager, release(pygame.K_p), frames=2)
            step(manager, press(pygame.K_SPACE))
            step(manager, release(pygame.K_SPACE), frames=2)
            step(manager, press(pygame.K_p))
            step(manager, release(pygame.K_p))
            pause_scene = manager.active_scene
            assert isinstance(pause_scene, PauseScene)
            assert manager.instant_replay()
            step(manager)
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step)
            assert manager.active_scene is pause_scene
            assert manager.previous_scene is live_scene
            step(manager)
            # A released voice is stopped for good (LiveAudio.release_voice)
            assert voice.state is not VoiceState.STOPPED


class TestPlaybackScopesAndTheJournal:
    """A playback scope suspends the live scene's journal, which bridges the gap afterwards."""

    def test_a_scope_suspends_the_journal_and_its_scene_keeps_none(self):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=2)
            journal = journal_of(manager)
            live_scene = active_counting_scene(manager)
            recording = journal.as_recording()
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
            assert manager.instant_replay_journal is journal
            frames_before = journal.frame_count
            step(manager, frames=2)
            # The scope's frames are not the scene's: the journal goes on after them
            assert journal.frame_count == frames_before + 2

    def test_two_instant_replays_in_a_row_the_second_across_the_first(self, mocker):
        """The second replays the first's request, its gap and the release held during it.

        Run as start() runs frames, with FPS events every other frame, so the frame clock and
        the FPS event timer the scene resumed with matter.
        """
        mocker.patch.object(LiveSources, 'frame_seconds', return_value=FRAME_SECONDS)
        with running_scene(InstantSelfReplayingScene) as manager:
            mocker.patch.dict(
                manager.OPTIONS, {'fps_log_interval_ms': FPS_EVENT_INTERVAL_MILLISECONDS}
            )
            live_scene = active_counting_scene(manager)
            step_finishing(manager, frames=3)
            journal = journal_of(manager)
            step_finishing(manager, press(pygame.K_r))
            step_finishing(manager, release(pygame.K_r))
            assert manager.playback_session is not None
            # A release during the scope is held for the live scene, which moves for it
            step_finishing(manager, press(pygame.K_SPACE))
            step_finishing(manager, release(pygame.K_SPACE))
            step_until_the_scope_ends(manager=manager, stepper=step_finishing)
            first_result = manager.last_playback_result
            assert first_result is not None
            assert first_result.divergence is None, first_result.report()
            assert manager.instant_replay_journal is journal
            step_finishing(manager, frames=3)
            # The first replay's request and its gap are in the journal
            frames = journal.as_recording().frames
            assert [
                frame[PLAYBACK_ANSWERS_FIELD] for frame in frames if PLAYBACK_ANSWERS_FIELD in frame
            ] == [[True]]
            (resumed_frame,) = [frame for frame in frames if RESUME_BRIDGE_FIELD in frame]
            # The player's releases (served in a playback) and the scene's own FPS event posted
            # before the scope (matched with the playback's post)
            assert {record['type'] for record in resumed_frame[REDELIVERED_EVENTS_FIELD]} == {
                pygame.KEYUP,
                FPSEVENT,
            }
            step_finishing(manager, press(pygame.K_r))
            step_finishing(manager, release(pygame.K_r))
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step_finishing)
            assert manager.active_scene is live_scene
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None, result.report()
            assert result.end_reason == 'end_of_recording'
            outcome = manager.last_playback_outcome
            assert outcome is not None
            assert outcome.reason == 'end_of_recording'

    def test_a_screen_shake_running_at_the_replay_is_cleared_in_the_journals_playback(self):
        """The scope's end stops the SCREEN shake; so does the playback at the resumed frame.

        Otherwise the screen shake would go on drawing from the shared shake stream in the
        playback, and the later WORLD shake would move the world sprite differently.
        """
        with running_scene(InstantShakingScene) as manager:
            live_scene = active_counting_scene(manager)
            step(manager, frames=2)
            step(manager, press(pygame.K_s))
            step(manager, release(pygame.K_s))
            assert manager.screen_shake.is_active
            step(manager, press(pygame.K_r))
            step(manager, release(pygame.K_r))
            step_until_the_scope_ends(manager=manager, stepper=step)
            first_result = manager.last_playback_result
            assert first_result is not None
            assert first_result.divergence is None, first_result.report()
            step(manager, press(pygame.K_w))
            step(manager, release(pygame.K_w), frames=4)
            step(manager, press(pygame.K_r))
            step(manager, release(pygame.K_r))
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step)
            assert manager.active_scene is live_scene
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None, result.report()
            assert result.end_reason == 'end_of_recording'

    def test_a_request_inside_a_playback_of_the_journal_requests_nothing(self):
        with running_scene(InstantSelfReplayingScene) as manager:
            live_scene = active_counting_scene(manager)
            step(manager, frames=2)
            step(manager, press(pygame.K_r))
            step(manager, release(pygame.K_r))
            while manager.playback_session is not None:
                # Inside it the rebuilt scene asks again (its recorded R press): answered from
                # the journal, it requests no nested scope
                assert manager._requested_playback is None
                step(manager)
            assert manager.active_scene is live_scene
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None, result.report()

    def test_a_demo_played_from_an_opted_in_scene_keeps_its_journal(self, tmp_path):
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=JOURNALED_FRAMES)
        with running_scene(InstantKeyReleaseScene) as manager:
            live_scene = active_counting_scene(manager)
            step(manager, frames=2)
            journal = journal_of(manager)
            assert start_playback_from_recording(
                manager=manager, path=recording_path, then=live_scene
            )
            step(manager)
            step(manager, KEY_RELEASE_DURING_SCOPE)
            step_until_the_scope_ends(manager=manager, stepper=step)
            step(manager, frames=2)
            assert manager.instant_replay_journal is journal
            play_journal(manager=manager, recording=journal.as_recording(), then=live_scene)


KEY_RELEASE_DURING_SCOPE = pygame.event.Event(
    pygame.KEYUP, key=pygame.K_SPACE, mod=0, unicode='', scancode=0
)


class TestTheBudget:
    """The journal is bounded by the frame time it holds, paused frames included."""

    def test_a_long_pause_passes_the_budget_and_drops_the_journal(self, mocker: MockerFixture):
        mocker.patch.object(
            InstantCountingScene,
            'MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS',
            PAUSE_BUDGET_FRAMES * FRAME_SECONDS,
        )
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=2)
            step(manager, press(pygame.K_p))
            step(manager, release(pygame.K_p))
            assert isinstance(manager.active_scene, PauseScene)
            journal = journal_of(manager)
            # Paused: no game time passes, but every frame must be fast-forwarded again
            step(manager, frames=PAUSE_BUDGET_FRAMES)
            assert journal.game_seconds < PAUSE_BUDGET_FRAMES * FRAME_SECONDS
            assert manager.instant_replay_journal is None


class TestPostsBeforeTheScene:
    """Code-posted events are tracked for the whole run, not only from the scene's setup."""

    def test_a_post_of_the_scene_left_plays_back(self):
        with running_scene(PostingInUpdateScene) as manager:
            step(manager, frames=SWITCH_FRAME + JOURNALED_FRAMES)
            live_scene = active_counting_scene(manager)
            assert isinstance(live_scene, InstantCountingScene)
            recording = journal_of(manager).as_recording()
            play_journal(manager=manager, recording=recording, then=live_scene)


class TestDevices:
    """The journal carries the device answers and descriptors a recording carries."""

    def test_joysticks_counted_and_opened_at_construction_and_mid_scene_play_back(
        self, mocker: MockerFixture, caplog
    ):
        fake_joysticks = [
            mocker.Mock(**{
                'get_instance_id.return_value': instance_id,
                'get_name.return_value': f'Fake Pad {instance_id}',
                'get_guid.return_value': 'guid',
                'get_numaxes.return_value': 2,
                'get_numbuttons.return_value': 4,
                'get_numhats.return_value': 1,
                'get_numballs.return_value': 0,
                'get_axis.return_value': 0.5,
                'get_button.return_value': False,
                'get_hat.return_value': (0, 1),
            })
            for instance_id in FAKE_INSTANCE_IDS
        ]
        mocker.patch.object(
            devices_module.pygame.joystick, 'get_count', return_value=FAKE_JOYSTICK_COUNT
        )
        mocker.patch.object(
            devices_module.pygame.joystick,
            'Joystick',
            side_effect=lambda device_index: fake_joysticks[device_index],
        )
        with running_scene(CameraFreeScene) as manager:
            manager.switch_to_scene(InstantJoystickScene(options=manager.OPTIONS))
            step(manager, frames=JOURNALED_FRAMES)
            live_scene = manager.active_scene
            assert isinstance(live_scene, InstantJoystickScene)
            play_journal(
                manager=manager, recording=journal_of(manager).as_recording(), then=live_scene
            )
        assert 'is not in the recording' not in caplog.text


class TestWatchedReplayOrigins:
    """Over a replay the journal takes each event's origin from the replay's merge."""

    def test_the_journal_uses_the_replays_batch_origins(self, tmp_path, mocker: MockerFixture):
        session_path = tmp_path / 'session.jsonl.gz'
        with running_scene(InstantPostingScene) as manager:
            engine = manager.game_engine
            assert engine is not None
            engine.start_trace_recording(path=session_path)
            step(manager, frames=JOURNALED_FRAMES)
            engine.stop_trace_recording()
        origins = mocker.spy(ReplaySources, 'last_batch_origins')
        with running_scene(
            InstantPostingScene, extra_arguments=['--replay-trace', str(session_path), '--headless']
        ) as manager:
            journal_pump = mocker.spy(manager, 'journal_pumped_events')
            step(manager, frames=JOURNALED_FRAMES)
        assert journal_pump.call_count == JOURNALED_FRAMES
        assert [call.kwargs['origins'] for call in journal_pump.call_args_list] == (
            origins.spy_return_list
        )


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


def assert_whole_display_update(*, updates: Any, flips: Any) -> None:
    """Check the one display update since the spies began was of the whole display.

    Args:
        updates: A spy on ``pygame.display.update``.
        flips: A spy on ``pygame.display.flip``.

    """
    whole_updates = [call for call in updates.call_args_list if not call.args and not call.kwargs]
    assert len(whole_updates) + flips.call_count == 1
    assert len(whole_updates) == updates.call_count


class EndingSupervisor:
    """Ends the playback scope in progress from the supervisor slot of a chosen frame."""

    def __init__(self: Self, *, manager: SceneManager, frame_number: int) -> None:
        """Watch for ``frame_number``.

        Args:
            manager: The running scene manager.
            frame_number: The frame whose slot ends the scope.

        """
        self.manager = manager
        self.frame_number = frame_number

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """End the scope on the chosen frame (implements glitchygames.supervision.Supervisor)."""
        del scene
        if frame_number == self.frame_number:
            self.manager.end_playback()


def scope_frames(*, manager: SceneManager) -> Iterator[PlaybackSources]:
    """Run frames while a playback scope plays, yielding its doors before each frame.

    Yields:
        The scope's doors, as the frame about to run reads them.

    """
    while (session := manager.playback_session) is not None:
        yield session.sources
        step(manager)


class TestInstantReplay:
    """SceneManager.instant_replay(): fast-forward, show the last seconds, return."""

    def test_instant_replay_shows_the_last_seconds_and_returns(self, mocker: MockerFixture):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=INSTANT_LIVE_FRAMES)
            live_scene = active_counting_scene(manager)
            ticked = live_scene.frames_ticked
            # _present_frame runs every frame; it shows the frame only when the doors present
            shown = mocker.spy(manager, '_show_frame')
            mocker.patch.object(
                InstantCountingScene, 'INSTANT_REPLAY_SECONDS', SHOWN_FRAMES * FRAME_SECONDS
            )
            assert manager.instant_replay()
            step(manager, frames=INSTANT_LIVE_FRAMES)
            assert manager.playback_session is None
            assert manager.active_scene is live_scene
            assert live_scene.frames_ticked == ticked
            # Only the last ten frames were shown
            assert shown.call_count == SHOWN_FRAMES
            outcome = manager.last_playback_outcome
            assert outcome is not None
            assert outcome.kind == INSTANT_PLAYBACK
            assert outcome.reason == 'end_of_recording'
            assert outcome.frames_played == INSTANT_LIVE_FRAMES

    def test_instant_replay_refused_past_the_budget(self, mocker: MockerFixture):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=INSTANT_LIVE_FRAMES)
            # Patched between frames: the journal is still kept, but now past the budget
            mocker.patch.object(
                InstantCountingScene,
                'MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS',
                REFUSING_BUDGET_FRAMES * FRAME_SECONDS,
            )
            assert manager.instant_replay_journal is not None
            assert not manager.instant_replay()
            step(manager)
            assert manager.playback_session is None

    def test_instant_replay_refused_without_a_journal(self):
        with running_scene(CountingScene) as manager:
            step(manager, frames=JOURNALED_FRAMES)
            assert not manager.instant_replay()
            step(manager)
            assert manager.playback_session is None

    def test_instant_replay_matches_the_live_frames(self):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=MATCHED_LIVE_FRAMES)
            assert manager.instant_replay()
            step(manager, frames=MATCHED_LIVE_FRAMES)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None, result.report()

    def test_fast_forward_frames_are_unpresented_unpaced_and_silent(self, mocker: MockerFixture):
        silenced = mocker.spy(FrameSilencer, 'silence_frame')
        finished = mocker.spy(FrameSilencer, 'finish')
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=INSTANT_LIVE_FRAMES)
            mocker.patch.object(
                InstantCountingScene, 'INSTANT_REPLAY_SECONDS', SHOWN_FRAMES * FRAME_SECONDS
            )
            assert manager.instant_replay()
            step(manager)
            assert manager.playback_session is not None
            fast_forward_frames = INSTANT_LIVE_FRAMES - SHOWN_FRAMES
            # From the scope's second frame on (the first was paced as the live doors paced it,
            # read before the scope was entered at the top of that frame)
            seen = [
                (sources.presents_frames, sources.paced_frame_seconds())
                for sources in scope_frames(manager=manager)
            ]
            assert (
                seen == [(False, 0.0)] * (fast_forward_frames - 1) + [(True, None)] * SHOWN_FRAMES
            )
            # Every fast-forwarded frame was silenced; the visible part plays its sounds
            assert silenced.call_count == fast_forward_frames
            # Once after the last fast-forwarded frame, once more (a no-op) as the scope ended
            assert finished.call_count == FINISHES_PER_FAST_FORWARDING_SCOPE

    def test_the_first_shown_frame_updates_the_whole_display(self, mocker: MockerFixture):
        """The display still shows the live scene: dirty rects alone would leave it there."""
        with running_scene(InstantCountingScene) as manager:
            assert manager.update_type == 'update'
            step(manager, frames=INSTANT_LIVE_FRAMES)
            mocker.patch.object(
                InstantCountingScene, 'INSTANT_REPLAY_SECONDS', SHOWN_FRAMES * FRAME_SECONDS
            )
            assert manager.instant_replay()
            step(manager, frames=INSTANT_LIVE_FRAMES - SHOWN_FRAMES)
            updates = mocker.spy(pygame.display, 'update')
            flips = mocker.spy(pygame.display, 'flip')
            step(manager)
            assert_whole_display_update(updates=updates, flips=flips)

    def test_the_first_live_frame_after_a_scope_updates_the_whole_display(
        self, mocker: MockerFixture
    ):
        with running_scene(InstantCountingScene) as manager:
            assert manager.update_type == 'update'
            step(manager, frames=JOURNALED_FRAMES)
            assert manager.instant_replay()
            step(manager)
            step_until_the_scope_ends(manager=manager, stepper=step)
            updates = mocker.spy(pygame.display, 'update')
            flips = mocker.spy(pygame.display, 'flip')
            step(manager)
            assert_whole_display_update(updates=updates, flips=flips)
            # Then dirty rects again
            step(manager)
            assert updates.call_args_list[-1].args

    def test_the_played_scenes_own_end_playback_is_ignored(self):
        """Its recorded call did nothing live (no scope), so it does nothing in the replay."""
        with running_scene(InstantEndingScene) as manager:
            live_scene = active_counting_scene(manager)
            step(manager, frames=2)
            step(manager, press(pygame.K_e))
            step(manager, release(pygame.K_e), frames=2)
            assert manager.instant_replay()
            step(manager)
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step)
            assert manager.active_scene is live_scene
            outcome = manager.last_playback_outcome
            assert outcome is not None
            assert outcome.reason == 'end_of_recording'

    def test_the_players_input_during_a_scope(self):
        with running_scene(InstantCountingScene) as manager:
            assert manager.playback_player_input is None
            step(manager, frames=JOURNALED_FRAMES)
            assert manager.instant_replay()
            step(manager)
            session = manager.playback_session
            assert session is not None
            assert manager.playback_player_input is session.sources.last_base_snapshot

    def test_a_real_press_does_not_end_an_instant_replay(self):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=JOURNALED_FRAMES)
            assert manager.instant_replay()
            step(manager)
            step(manager, press(pygame.K_SPACE))
            assert manager.playback_session is not None
            step(manager, release(pygame.K_SPACE), frames=JOURNALED_FRAMES)
            outcome = manager.last_playback_outcome
            assert outcome is not None
            assert outcome.reason == 'end_of_recording'

    def test_the_game_ends_an_instant_replay_between_frames(self):
        with running_scene(InstantCountingScene) as manager:
            live_scene = active_counting_scene(manager)
            step(manager, frames=JOURNALED_FRAMES)
            assert manager.instant_replay()
            step(manager, frames=2)
            assert manager.playback_session is not None
            manager.end_playback()
            assert manager.playback_session is None
            assert manager.active_scene is live_scene
            outcome = manager.last_playback_outcome
            assert outcome is not None
            assert outcome.reason == 'ended_by_game'
            assert outcome.frames_played == 2
            # Nothing to end: nothing happens
            manager.end_playback()
            assert manager.last_playback_outcome is outcome

    def test_a_scope_ended_while_fast_forwarding_ends_the_silence(self, mocker: MockerFixture):
        with running_scene(InstantCountingScene) as manager:
            step(manager, frames=INSTANT_LIVE_FRAMES)
            mocker.patch.object(
                InstantCountingScene, 'INSTANT_REPLAY_SECONDS', SHOWN_FRAMES * FRAME_SECONDS
            )
            assert manager.instant_replay()
            step(manager, frames=2)
            session = manager.playback_session
            assert session is not None
            assert session.sources.is_fast_forwarding
            finished = mocker.spy(FrameSilencer, 'finish')
            manager.end_playback()
            assert finished.call_count == 1

    def test_the_game_ends_an_instant_replay_inside_a_frame_at_its_end(self):
        """Called during a frame (a supervisor, say), the scope ends once the frame ended."""
        with running_scene(InstantCountingScene) as manager:
            live_scene = active_counting_scene(manager)
            step(manager, frames=JOURNALED_FRAMES)
            assert manager.instant_replay()
            manager.add_supervisor(
                supervisor=EndingSupervisor(manager=manager, frame_number=manager.frame_number + 1)
            )
            step(manager)
            assert manager.playback_session is not None
            step(manager)
            assert manager.playback_session is None
            assert manager.active_scene is live_scene
            outcome = manager.last_playback_outcome
            assert outcome is not None
            assert outcome.reason == 'ended_by_game'
            # The frame it was asked in was played and compared whole
            assert outcome.frames_played == 2
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None

    def test_a_replay_the_game_asked_for_plays_back_across_in_a_later_one(
        self, mocker: MockerFixture
    ):
        """The game's own request after a goal is answered from the journal in the later one.

        The later one fast-forwards across the first (only its last frames are shown).
        """
        with running_scene(InstantGoalScene) as manager:
            live_scene = active_counting_scene(manager)
            step(manager, frames=GOAL_TICK)
            step(manager)
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step)
            first_result = manager.last_playback_result
            assert first_result is not None
            assert first_result.divergence is None, first_result.report()
            step(manager, frames=JOURNALED_FRAMES)
            mocker.patch.object(
                InstantGoalScene, 'INSTANT_REPLAY_SECONDS', SHOWN_FRAMES_AFTER_GOAL * FRAME_SECONDS
            )
            assert manager.instant_replay()
            step(manager)
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step)
            assert manager.active_scene is live_scene
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None, result.report()
            assert result.end_reason == 'end_of_recording'

    @pytest.mark.parametrize('viewing_arguments', [['--headless'], []], ids=['headless', 'watched'])
    def test_a_replayed_session_with_instant_replays_matches(
        self, tmp_path, mocker: MockerFixture, viewing_arguments: list[str]
    ):
        mocker.patch.object(
            InstantGoalScene, 'INSTANT_REPLAY_SECONDS', SHOWN_FRAMES_AFTER_GOAL * FRAME_SECONDS
        )
        session_path = tmp_path / 'session.jsonl.gz'
        with running_scene(InstantGoalScene) as manager:
            engine = manager.game_engine
            assert engine is not None
            engine.start_trace_recording(path=session_path)
            self._play(manager=manager)
            engine.stop_trace_recording()
        replay_arguments = ['--replay-trace', str(session_path), *viewing_arguments]
        with running_scene(InstantGoalScene, extra_arguments=replay_arguments) as manager:
            engine = manager.game_engine
            assert engine is not None
            replay_sources = engine.replay_sources
            assert replay_sources is not None
            self._play(manager=manager)
            replay_sources.finish_run()
            assert replay_sources.result.divergence is None, replay_sources.result.report()

    @staticmethod
    def _play(*, manager: SceneManager) -> None:
        """Play to the goal's instant replay, then show one more on R."""
        step(manager, frames=GOAL_TICK + 1)
        assert manager.playback_session is not None
        step_until_the_scope_ends(manager=manager, stepper=step)
        step(manager, frames=2)
        step(manager, press(pygame.K_r))
        step(manager, release(pygame.K_r))
        assert manager.playback_session is not None
        step_until_the_scope_ends(manager=manager, stepper=step)
        step(manager, frames=2)


class TestSupervisorsInAScope:
    """Supervisors added while a playback scope plays belong to it and end with it."""

    def test_a_supervisor_added_during_a_scope_is_removed_when_it_ends(self):
        live_supervisor = FrameCountingSupervisor()
        scope_supervisor = FrameCountingSupervisor()
        with running_scene(InstantCountingScene) as manager:
            manager.add_supervisor(supervisor=live_supervisor)
            step(manager, frames=INSTANT_LIVE_FRAMES)
            assert manager.instant_replay()
            step(manager)
            assert manager.playback_session is not None
            manager.add_supervisor(supervisor=scope_supervisor)
            step_until_the_scope_ends(manager=manager, stepper=step)
            scope_frames_seen = scope_supervisor.frames_seen
            live_frames_before = live_supervisor.frames_seen
            step(manager, frames=2)
            manager.remove_supervisor(supervisor=live_supervisor)
        assert scope_frames_seen > 0
        assert scope_supervisor.frames_seen == scope_frames_seen
        assert live_supervisor.frames_seen == live_frames_before + 2

    def test_a_ghost_recorder_made_by_the_rebuilt_scene_ends_with_the_scope(self, mocker):
        mocker.patch.object(GhostRecordingScene, 'recorders', [])
        with running_scene(GhostRecordingScene) as manager:
            live_scene = manager.active_scene
            step(manager, frames=INSTANT_LIVE_FRAMES)
            assert manager.instant_replay()
            # The scope begins at the start of the next frame
            step(manager)
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step)
            live_recorder, rebuilt_recorder = GhostRecordingScene.recorders
            rebuilt_on_frame = mocker.spy(rebuilt_recorder, 'on_frame')
            step(manager, frames=2)
            assert manager.active_scene is live_scene
            assert live_scene is not None
            live_game_time = live_scene.game_time
            live_track = live_recorder.finish()
        assert rebuilt_on_frame.call_count == 0
        # The rebuilt scene's recorder sampled nothing: no live frame, no frame of its own
        assert rebuilt_recorder.finish().samples == ()
        live_game_seconds = [recorded.game_seconds for recorded in live_track.samples]
        assert live_game_seconds == sorted(set(live_game_seconds))
        assert live_game_seconds[-1] == pytest.approx(live_game_time)
        # Every live frame but none of the scope's
        assert len(live_track.samples) == INSTANT_LIVE_FRAMES + 2

    def test_a_supervisor_a_live_supervisor_adds_during_a_scope_stays(self):
        """Only the scope's code owns what it adds: a live supervisor's additions are live."""
        added = FrameCountingSupervisor()
        live_supervisor = SupervisorAddingSupervisor(on_call=INSTANT_LIVE_FRAMES + 2, added=added)
        with running_scene(InstantCountingScene) as manager:
            manager.add_supervisor(supervisor=live_supervisor)
            step(manager, frames=INSTANT_LIVE_FRAMES)
            assert manager.instant_replay()
            step(manager, frames=2)
            assert manager.playback_session is not None
            assert added.frames_seen == 0
            step_until_the_scope_ends(manager=manager, stepper=step)
            frames_seen_in_the_scope = added.frames_seen
            step(manager, frames=2)
            manager.remove_supervisor(supervisor=live_supervisor)
            manager.remove_supervisor(supervisor=added)
        assert frames_seen_in_the_scope > 0
        assert added.frames_seen == frames_seen_in_the_scope + 2

    def test_a_control_event_handler_the_rebuilt_scene_adds_ends_with_the_scope(self, mocker):
        mocker.patch.object(HandlerAddingScene, 'breakpoints_seen', [])
        with running_scene(HandlerAddingScene) as manager:
            live_scene = manager.active_scene
            step(manager, frames=INSTANT_LIVE_FRAMES)
            assert manager.instant_replay()
            # The scope begins at the start of the next frame
            step(manager)
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step)
            step(manager)
            manager.record_control_event(kind=BREAKPOINT_KIND, data={'label': 'after'})
        # Only the live scene's handler is left to see it
        assert HandlerAddingScene.breakpoints_seen == [live_scene]

    def test_a_supervisor_the_playback_scenes_cleanup_adds_ends_with_the_scope(
        self, tmp_path, mocker
    ):
        mocker.patch.object(CleanupSupervisingScene, 'added_in_cleanup', [])
        recording_path = record_counting_scene(
            tmp_path=tmp_path, frames=JOURNALED_FRAMES, scene_class=CleanupSupervisingScene
        )
        with running_scene(CountingScene) as manager:
            live_scene = active_counting_scene(manager)
            assert start_playback_from_recording(
                manager=manager, path=recording_path, then=live_scene
            )
            step(manager)
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step)
            (added_in_cleanup,) = CleanupSupervisingScene.added_in_cleanup
            step(manager, frames=2)
            assert added_in_cleanup.frames_seen == 0
            assert added_in_cleanup not in manager._supervisors


class TestControlEventsAcrossAScope:
    """Inside a scope the installed doors' re-applied control events apply, not the recording's."""

    def test_a_journaled_breakpoint_is_not_applied_again_in_the_instant_replay(self):
        breakpoints_seen: list[object] = []
        with running_scene(InstantCountingScene) as manager:
            manager.add_control_event_handler(kind=BREAKPOINT_KIND, handler=breakpoints_seen.append)
            step(manager, frames=2)
            # A live supervisor's breakpoint, in a frame the journal keeps
            manager.record_control_event(kind=BREAKPOINT_KIND, data={'label': 'live'})
            step(manager, frames=INSTANT_LIVE_FRAMES)
            assert manager.instant_replay()
            step(manager)
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None
        assert len(breakpoints_seen) == 1

    def test_a_session_breakpoint_on_a_scope_frame_applies_in_its_replay(self, tmp_path):
        """A replay of the session pauses at a bookmark on a frame a demo was playing in."""
        recording_path = record_counting_scene(tmp_path=tmp_path, frames=JOURNALED_FRAMES)
        session_path = tmp_path / 'session.jsonl.gz'

        def play_in_the_session(manager: SceneManager) -> None:
            step(manager, frames=2)
            start_playback_from_recording(
                manager=manager, path=recording_path, then=manager.active_scene
            )
            step(manager, frames=JOURNALED_FRAMES + 2)
            assert manager.playback_session is None

        with running_scene(CountingScene) as manager:
            engine = manager.game_engine
            assert engine is not None
            engine.start_trace_recording(path=session_path)
            play_in_the_session(manager)
            engine.stop_trace_recording()
        trace = read_trace_result(path=session_path).trace
        (scope_start_frame,) = [
            index
            for index, frame in enumerate(trace['frames'])
            if frame.get('control_events', [{}])[0].get('kind') == 'playback'
        ]
        # A bookmark on a frame the demo plays in (no control event of its own)
        scope_frame = scope_start_frame + 2
        trace['frames'][scope_frame]['control_events'] = [
            {'kind': BREAKPOINT_KIND, 'label': 'bookmark'}
        ]
        write_trace(trace=trace, path=session_path)
        breakpoints_seen: list[object] = []
        with running_scene(
            CountingScene, extra_arguments=['--replay-trace', str(session_path), '--headless']
        ) as manager:
            engine = manager.game_engine
            assert engine is not None
            replay_sources = engine.replay_sources
            assert replay_sources is not None
            manager.add_control_event_handler(kind=BREAKPOINT_KIND, handler=breakpoints_seen.append)
            play_in_the_session(manager)
            replay_sources.finish_run()
            assert replay_sources.result.divergence is None
        assert len(breakpoints_seen) == 1


class TestScopePostsAndTheJournal:
    """A playback scene's posts still queued as its scope ends never reach the live scene."""

    def test_a_goal_posted_in_update_asks_for_one_instant_replay(self, mocker):
        mocker.patch.object(GoalInUpdateScene, 'requests', [])
        with running_scene(GoalInUpdateScene) as manager:
            step(manager, frames=INSTANT_LIVE_FRAMES * 4)
            assert manager.playback_session is None
        live_requests = [
            granted for in_a_scope, granted in GoalInUpdateScene.requests if not in_a_scope
        ]
        assert live_requests == [True]

    def test_a_later_replay_across_a_scope_with_dropped_posts_matches(self, mocker):
        """The journal resumes after the scope as if the dropped posts had never been made.

        The scene's own posts every tick are matched in the playback: a dropped post counted as
        an earlier event of the resumed frame would make the next one served, not matched.
        """
        mocker.patch.object(GoalInUpdateScene, 'requests', [])
        with running_scene(GoalInUpdatePostingScene) as manager:
            step(manager, frames=INSTANT_LIVE_FRAMES)
            assert manager.playback_session is None
            first_result = manager.last_playback_result
            assert first_result is not None
            assert first_result.divergence is None
            step(manager, frames=JOURNALED_FRAMES)
            # A second instant replay plays the journal across the first one
            assert manager.instant_replay()
            step(manager)
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None, result.report()
            assert result.end_reason == 'end_of_recording'

    @pytest.mark.parametrize('poster', [post_event, post_input_event])
    @pytest.mark.parametrize('ends_the_scope', [True, False])
    def test_a_later_replay_across_a_scope_with_a_live_supervisors_post_matches(
        self, ends_the_scope, poster
    ):
        """The live supervisor's post reaches the live scene after the scope, as journaled."""
        with running_scene(InstantUserEventScene) as manager:
            step(manager, frames=JOURNALED_FRAMES)
            live_scene = active_counting_scene(manager)
            supervisor = LivePostingSupervisor(ends_the_scope=ends_the_scope, poster=poster)
            manager.add_supervisor(supervisor=supervisor)
            assert manager.instant_replay()
            step(manager)
            step_until_the_scope_ends(manager=manager, stepper=step)
            marker_before = live_scene.marker.rect.y
            step(manager, frames=JOURNALED_FRAMES)
            # Delivered once, to the live scene
            assert live_scene.marker.rect.y == marker_before + 1
            # A second instant replay plays the journal across the first one
            assert manager.instant_replay()
            step(manager)
            assert manager.playback_session is not None
            step_until_the_scope_ends(manager=manager, stepper=step)
            manager.remove_supervisor(supervisor=supervisor)
            result = manager.last_playback_result
            assert result is not None
            assert result.divergence is None, result.report()
            assert result.end_reason == 'end_of_recording'


class TestInputPostsAndTheJournal:
    """post_input_event is input: an instant replay serves it, whoever posted it (BUGS.md #84)."""

    def test_a_live_supervisors_input_post_is_served_by_a_later_instant_replay(self):
        """The journal holds it as input, so the played scene gets it without the supervisor."""
        with running_scene(InstantUserEventScene) as manager:
            live_scene = active_counting_scene(manager)
            supervisor = InputPostingSupervisor(on_call=2)
            manager.add_supervisor(supervisor=supervisor)
            marker_rect = live_scene.marker.rect
            assert marker_rect is not None
            marker_before = marker_rect.y
            step(manager, frames=JOURNALED_FRAMES)
            assert marker_rect.y == marker_before + 1
            journaled_origins = [
                record['origin']
                for record in event_records(frames=journal_of(manager).as_recording().frames)
                if record['attributes'].get('input_from_supervisor') == 1
            ]
            assert journaled_origins == [EXTERNAL_ORIGIN]
            play_journal(
                manager=manager, recording=journal_of(manager).as_recording(), then=live_scene
            )
            assert supervisor.posts == 1

    def test_a_scene_added_supervisors_input_post_arrives_once_in_an_instant_replay(self):
        """The played scene adds it again; its copy is dropped and the journaled one served."""
        InputSupervisingScene.posts_by_supervisors = 0
        with running_scene(InputSupervisingScene) as manager:
            live_scene = active_counting_scene(manager)
            assert isinstance(live_scene, InputSupervisingScene)
            step(manager, frames=JOURNALED_FRAMES)
            play_journal(
                manager=manager, recording=journal_of(manager).as_recording(), then=live_scene
            )
            # One post live, one by the played scene's own supervisor
            assert InputSupervisingScene.posts_by_supervisors == 2


class TestInputPostsAtASceneStart:
    """An input post pending as a scene's logic begins is not one of its earlier posts."""

    def test_an_input_post_queued_for_the_first_logic_frame_is_not_counted(self):
        """Counted, the replay would serve the scene's own first post and then see it again."""
        with running_scene(SwitchingToInstantPostingScene) as manager:
            # Posts in the switching frame's supervisor slot, after the switch was requested
            manager.add_supervisor(supervisor=InputPostingSupervisor(on_call=SWITCH_FRAME))
            step(manager, frames=SWITCH_FRAME + JOURNALED_FRAMES)
            live_scene = active_counting_scene(manager)
            assert isinstance(live_scene, InstantPostingScene)
            start = live_scene.scene_start
            assert start is not None
            assert start.first_logic_frame is not None
            assert start.first_logic_frame.earlier_internal_event_count == 0
            recording = journal_of(manager).as_recording()
            first_batch = recording.frames[recording.start_frame]['event_batches'][0]
            assert [record['origin'] for record in first_batch] == [
                EXTERNAL_ORIGIN,
                INTERNAL_ORIGIN,
            ]
            play_journal(manager=manager, recording=recording, then=live_scene)


class TestFastForwardFrameCount:
    """How many of a recording's frames an instant replay plays before the ones it shows."""

    def test_the_frames_before_the_shown_seconds_are_fast_forwarded(self):
        frames = [{'dt': 0.0}] + [{'dt': FRAME_SECONDS}] * INSTANT_LIVE_FRAMES
        assert (
            fast_forward_frame_count(
                frames=frames, start_frame=1, shown_seconds=SHOWN_FRAMES * FRAME_SECONDS
            )
            == INSTANT_LIVE_FRAMES - SHOWN_FRAMES
        )

    def test_a_frame_partly_inside_the_shown_seconds_is_fast_forwarded(self):
        frames = [{'dt': FRAME_SECONDS}] * INSTANT_LIVE_FRAMES
        assert (
            fast_forward_frame_count(
                frames=frames, start_frame=0, shown_seconds=(SHOWN_FRAMES + 0.5) * FRAME_SECONDS
            )
            == INSTANT_LIVE_FRAMES - SHOWN_FRAMES
        )

    def test_more_seconds_than_recorded_fast_forward_nothing(self):
        frames = [{'dt': FRAME_SECONDS}] * SHOWN_FRAMES
        assert fast_forward_frame_count(frames=frames, start_frame=0, shown_seconds=10.0) == 0
