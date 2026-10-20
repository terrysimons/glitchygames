"""In-game playback: a running game plays a recording to a rebuilt scene, then goes on.

Demos and instant replays run inside a playback scope, not a new engine run
(plans/2026-10-19-gameplay-replay.md, section 5.2). The rules:

1. Starting (``start_playback``; ``start_playback_from_recording`` reads a file first): the
   frame played first (``PlaybackOptions.start_frame``) must hold a ``scene_start``
   (glitchygames/scene_start.py) with its first logic frame (rule 7 there: a recording writes
   a start on the scene's first logic frame, so the start's frame is where its logic began),
   and its scene class must be found among the loaded ``Scene`` subclasses by name; otherwise
   nothing starts (logged; False), as for a recording that cannot be replayed (a malformed one
   included). The replay sources are made (``playback_replay_sources``, rule 18 of
   glitchygames/replay/driver.py) and the scope is requested (``SceneManager.
   request_playback``): the scene manager enters it at the start of the next frame, so the
   rebuilt scene's first frame is a whole frame, as recorded, and the frame that asked ends on
   the live doors. A request made while a transition plays waits for its end. A request made
   in a frame whose end switches scenes (``next_scene``) is dropped, logged: the scene to
   return to has gone. Scopes do not nest.
2. Entering (``SceneManager._enter_playback``): the random streams, the frame clock and the FPS
   event timer are saved (``PlaybackRequest.begin_session``); the live scene is stashed without
   ``cleanup()``; ``PlaybackSources`` are pushed on top of the installed doors
   (``push_scoped_sources``; glitchygames/sources.py); a ``playback`` control event is
   recorded (a marker: replaying the session starts the scope again from the recorded input,
   so it is compared, never applied again); the scene is rebuilt (``rebuild_scene``) and made
   active as a switch would, a transition's arrival step is repeated for a scene that arrived
   by one; then the streams, the frame clock and the FPS event timer are set as the scene's
   first logic frame began, the frame takes the recording's dt, and the current polled input
   becomes the recording's before that frame (idle before frame 0), so the live input never
   leaks in.
3. Frames: ``PlaybackSources`` serve the recording to the scene (rule 5) and the scene
   manager runs every frame as always, paced and presented by the installed doors (a demo
   plays at the game's speed).
4. Ending: after each frame, the scope ends when its doors found a reason
   (``PlaybackSources.end_reason``): the player's press (``exit_on_input``: any key or button,
   ``PLAYBACK_EXIT_EVENT_TYPES``), the recording's quit (its window's QUIT or the playback
   scene's own ``quit_game()``: the scope ends, the game does not quit), or the recording's end
   or divergence (the replay stops there; a playback never pauses). An error in the scope's
   part of a frame (its frame, the comparison, or entering) ends it too, logged
   (``SceneManager._run_frame`` contains it); an error of the installed doors (a session
   recorder that cannot write) propagates as it would outside a scope. The run's end
   (``SceneManager.terminate``, after the player's QUIT) ends a scope in progress first and
   drops a requested one, so the live scene is the one torn down. Ending
   (``SceneManager._exit_playback``) keeps the replay's result
   (``SceneManager.last_playback_result``) and a ``PlaybackOutcome``
   (``SceneManager.last_playback_outcome``: the kind, the reason and the frames played), cleans
   up the playback's scene, pops the scoped doors, restores the streams, the frame clock, the
   FPS event timer and the live polled input (the installed doors' latest snapshot), posts
   again the live game's posts the scope drained and hands back the player's held events (rule
   5), then makes the live scene active again exactly as it was (no ``setup()`` again: only its
   snap mode, event proxies, caption and a full redraw), or switches to ``then`` when that is
   another scene. The frame that ends the scope still finishes afterwards, so the restored
   live frame clock resumes one frame later (it advances by that frame's dt).
5. The scoped doors (``PlaybackSources``):

   - ``pump_events``: the installed doors pump once per pump of the frame (the real queue live;
     the session's recorded batch when the session is replayed, so the exit press replays
     too). Their batch is sorted with the internal-post tracker. The player's QUIT (and one the
     live game posted) is kept: it quits the game. Internal events, the playback scene's own
     posts, go to the replay (``ReplaySources.pump_events(real_events=...)``), which matches
     them with the recorded ones. Internal events posted before the scope began (the live
     game's last FPS event, say) are held (``held_live_posts``) and posted again when the scope
     ends: they are the live game's, and would be divergences of the recording's first frame.
     External events reach only the exit check, never the scene; of them, the ones the live
     game must not lose (releases, device and window events, ``PLAYBACK_HELD_EVENT_TYPES``)
     are held (``held_live_events``) and delivered before the first pump after the scope
     (``sources.redeliver_events``); presses and motion are dropped. The batch is the
     replay's (recorded external events, matched internal ones) without any QUIT (a QUIT in
     it ends the scope: ``recording_quit``), then the kept QUIT.
   - ``input_snapshot``: the installed doors' snapshot is read (a recording of the session
     records the player's polled input; it is kept as ``last_base_snapshot``), the replay's is
     returned.
   - ``frame_seconds``: the replay's (the recording's dt; past its end, the installed doors'
     measurement), asked after the installed doors were asked as always.
   - ``saves``, ``devices``, ``wall_clock_time``, ``control_events_for_frame``,
     ``random_seed``, ``opened_save_namespaces``: the replay's (saves are a sandbox seeded
     from the scene start's save view: real saves are never touched).
   - ``end_frame`` is ``compare_frame`` (the replay compares the frame, its ``playback``
     marker left out: the recording never holds it), then the installed doors' ``end_frame``
     (a recording of the session writes it; glitchygames/recording.py, Playback scopes). The
     scene manager calls the two itself, so only the comparison's errors end the scope.
   - ``captures_scene_starts`` is True; ``stop_requested``, pacing, holding, presenting and
     the overlay are the installed doors' (the scope never stops the run).

Limits: a scene must be rebuildable from its start (``Scene.replay_arguments``). Of a scene
that arrived by a transition, the arrival step is repeated, but the events the ride delivered
to it (releases, window and device events) are not: a scene they change diverges. The
first logic frame's earlier posts are counted from the internal-post tracker, so they are
exact while posts are tracked (while recording or replaying).
"""

from __future__ import annotations

import collections
import logging
from typing import TYPE_CHECKING, Any, Final, Literal, Self

import pygame
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from glitchygames.events import AUDIO_EVENTS, WINDOW_EVENTS
from glitchygames.input.state import current_input
from glitchygames.randomness import capture_stream_states
from glitchygames.recording import (
    INTERNAL_ORIGIN,
    SCENE_START_FIELD,
    event_origin,
    pending_internal_posts,
    take_internal_post,
)
from glitchygames.replay.driver import playback_replay_sources
from glitchygames.scene_start import FirstLogicFrame, SceneStart
from glitchygames.scenes import Scene
from glitchygames.sources import active_sources, frame_clock_seconds
from glitchygames.supervision import PLAYBACK_KIND
from glitchygames.tracing import FRAMES_FIELD, TraceFormatError, read_trace_result

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime
    from pathlib import Path

    from glitchygames.input.devices import DeviceRegistry
    from glitchygames.input.state import InputSnapshot
    from glitchygames.replay.driver import ReplaySources
    from glitchygames.scenes import SceneManager
    from glitchygames.sources import EngineSources
    from glitchygames.state.manager import SaveManager
    from glitchygames.supervision import ControlEvent

LOG = logging.getLogger('game.replay.playback')

# What a scope plays: an attract-mode demo, or an instant replay of the live scene
type PlaybackKind = Literal['demo', 'instant']
DEMO_PLAYBACK: Final = 'demo'
INSTANT_PLAYBACK: Final = 'instant'
# Why a scope ended (PlaybackOutcome.reason)
type PlaybackEndReason = Literal[
    'exit_input', 'recording_quit', 'end_of_recording', 'truncated', 'diverged', 'error', 'quit'
]

# The player's presses that end a playback started with exit_on_input (spec 5.2: any key or
# button)
PLAYBACK_EXIT_EVENT_TYPES: Final = frozenset({
    pygame.KEYDOWN,
    pygame.MOUSEBUTTONDOWN,
    pygame.JOYBUTTONDOWN,
    pygame.CONTROLLERBUTTONDOWN,
})
# The player's events the live game must not lose while a scope plays: releases (a key or
# button let go during a demo would otherwise stay held), device arrivals and removals, and
# window and app events. Held, then delivered after the scope (rule 5)
PLAYBACK_HELD_EVENT_TYPES: Final = frozenset({
    pygame.KEYUP,
    pygame.MOUSEBUTTONUP,
    pygame.JOYBUTTONUP,
    pygame.CONTROLLERBUTTONUP,
    pygame.CONTROLLERTOUCHPADUP,
    pygame.FINGERUP,
    pygame.JOYDEVICEADDED,
    pygame.JOYDEVICEREMOVED,
    pygame.CONTROLLERDEVICEADDED,
    pygame.CONTROLLERDEVICEREMOVED,
    pygame.CONTROLLERDEVICEREMAPPED,
    pygame.ACTIVEEVENT,
    pygame.VIDEORESIZE,
    pygame.VIDEOEXPOSE,
    *AUDIO_EVENTS,
    *WINDOW_EVENTS,
})


class PlaybackOptions(BaseModel):
    """How a playback scope plays (read-only).

    Attributes:
        exit_on_input: True to end the scope at any key or button press (a demo).
        kind: What the scope plays (the ``playback`` control event's ``source``).
        start_frame: The recording frame played first; it must hold a ``scene_start``.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    exit_on_input: bool = False
    kind: PlaybackKind = DEMO_PLAYBACK
    start_frame: int = Field(default=0, ge=0)


# A playback with no options: no exit on input, a demo, from the recording's first frame
DEFAULT_PLAYBACK_OPTIONS = PlaybackOptions()


class PlaybackSources:
    """A playback scope's doors (implements glitchygames.sources.EngineSources; rule 5).

    Attributes:
        base: The installed doors underneath (live, recording or a replay of the session).
        replay: The replay serving the recording to the playback's scene.
        exit_on_input: True when any key or button press ends the scope.
        exit_requested: True once such a press arrived.
        recording_quit: True once the recording asked to quit (its window's QUIT, or the
            playback scene's own ``quit_game()``): the scope ends, the game does not quit.
        captures_scene_starts: True: scenes built inside the scope capture their starts.
        random_seed: The recording's master seed.
        frames_played: How many frames the replay compared so far.
        end_reason: Why the scope should end now, or None while it plays on: the first found
            of the player's exit press (``'exit_input'``) and the recording's quit
            (``'recording_quit'``), found by the frame's pumps, then the replay's end
            (``'end_of_recording'``, ``'truncated'`` or ``'diverged'``), found by
            ``compare_frame``.
        last_base_snapshot: The installed doors' latest polled input (the live input as the
            scope began, then each frame's): the live game's input when the scope ends.
        held_live_posts: Events the live game posted before the scope that its pumps drained:
            posted again when the scope ends.
        held_live_events: The player's events the live game must not lose (releases, device
            and window events, ``PLAYBACK_HELD_EVENT_TYPES``), drained by the scope's pumps:
            delivered before the first pump after the scope.

    """

    def __init__(
        self: Self, *, base: EngineSources, replay: ReplaySources, exit_on_input: bool
    ) -> None:
        """Wrap the installed doors and a replay.

        Args:
            base: The installed doors.
            replay: The replay sources (``playback_replay_sources``).
            exit_on_input: True to end the scope at any key or button press.

        """
        self.base = base
        self.replay = replay
        self.exit_on_input = exit_on_input
        self.exit_requested = False
        self.recording_quit = False
        # The EngineSources property, as a plain attribute: set once, for the whole scope
        self.captures_scene_starts = True
        self.random_seed = replay.random_seed
        self.frames_played = 0
        self.end_reason: PlaybackEndReason | None = None
        self.last_base_snapshot: InputSnapshot = current_input()
        self.held_live_posts: list[pygame.event.Event] = []
        self.held_live_events: list[pygame.event.Event] = []
        # Posts the live game made that no pump has returned yet as the scope began (rule 5)
        self._posts_before_scope: list[tuple[int, dict[str, Any]]] = []
        self._has_pumped = False

    def _note_end(self: Self, *, reason: PlaybackEndReason) -> None:
        """Keep why the scope should end; the first reason found wins (``end_reason``)."""
        if self.end_reason is None:
            self.end_reason = reason

    @property
    def opened_save_namespaces(self: Self) -> Mapping[str, SaveManager]:
        """The replay's sandboxed save stores, by namespace."""
        return self.replay.opened_save_namespaces

    @property
    def stop_requested(self: Self) -> bool:
        """Whether the installed doors want the run to end (the scope never stops it)."""
        return self.base.stop_requested

    @property
    def presents_frames(self: Self) -> bool:
        """Whether the installed doors present the frames as they run."""
        return self.base.presents_frames

    @property
    def draws_overlay(self: Self) -> bool:
        """Whether the installed doors draw an overlay of their own."""
        return self.base.draws_overlay

    def on_installed(self: Self) -> None:
        """Note the live game's pending posts and input, then let the replay own the tracker."""
        self._posts_before_scope = list(pending_internal_posts())
        self._has_pumped = False
        self.last_base_snapshot = current_input()
        self.replay.on_installed()

    def on_uninstalled(self: Self) -> None:
        """Let the replay give up the post tracker."""
        self.replay.on_uninstalled()

    def pump_events(self: Self) -> list[pygame.event.Event]:
        """Pump the installed doors once; serve the replay's batch plus the window's QUIT (rule 5).

        Returns:
            The replay's batch in its recorded order without any QUIT (the recording's quit
            ends the scope instead), then any QUIT the installed doors read.

        """
        pending = pending_internal_posts()
        posted_before_pump = list(pending)
        base_events = self.base.pump_events()
        # The posts the live game made before the scope come first (pending is in posting
        # order, and nothing pumped between the scope's start and its first pump)
        is_first_pump = not self._has_pumped
        self._has_pumped = True
        live_post_count = len(self._posts_before_scope) if is_first_pump else 0
        scope_posts = posted_before_pump[live_post_count:]
        internal_events, quit_events = self._sort_base_events(
            base_events=base_events,
            live_posts=posted_before_pump[:live_post_count],
            scope_posts=list(scope_posts),
            is_first_pump=is_first_pump,
        )
        # The installed doors' recorder (if any) consumed the posts it matched; the replay
        # classifies the internal events again, from the scope's posts alone
        pending[:] = scope_posts
        replay_batch: list[pygame.event.Event] = []
        for event in self.replay.pump_events(real_events=internal_events):
            if event.type == pygame.QUIT:
                self.recording_quit = True
                self._note_end(reason='recording_quit')
            else:
                replay_batch.append(event)
        return [*replay_batch, *quit_events]

    def _sort_base_events(
        self: Self,
        *,
        base_events: list[pygame.event.Event],
        live_posts: list[tuple[int, dict[str, Any]]],
        scope_posts: list[tuple[int, dict[str, Any]]],
        is_first_pump: bool,
    ) -> tuple[list[pygame.event.Event], list[pygame.event.Event]]:
        """Sort the installed doors' batch for the replay, the game and the exit check (rule 5).

        Holds the live game's posts and the events it must not lose (``held_live_posts``,
        ``held_live_events``).

        Args:
            base_events: The installed doors' batch.
            live_posts: Posts the live game made before the scope (matches are removed).
            scope_posts: Posts made since the scope began (matches are removed).
            is_first_pump: True for the scope's first pump, whose untracked internal events
                were posted before the scope.

        Returns:
            The internal events for the replay, and the QUIT events for the game.

        """
        internal_events: list[pygame.event.Event] = []
        quit_events: list[pygame.event.Event] = []
        for event in base_events:
            if event.type == pygame.QUIT and not take_internal_post(
                event=event, pending=scope_posts
            ):
                # The player's (or the live game's own) quit request still quits the game
                take_internal_post(event=event, pending=live_posts)
                quit_events.append(event)
            elif event.type == pygame.QUIT:
                internal_events.append(event)
            elif take_internal_post(event=event, pending=live_posts):
                self.held_live_posts.append(event)
            elif take_internal_post(event=event, pending=scope_posts):
                internal_events.append(event)
            elif event_origin(event=event, pending=[]) == INTERNAL_ORIGIN:
                # Internal by type alone: on the first pump, posted before the scope began
                if is_first_pump:
                    self.held_live_posts.append(event)
                else:
                    internal_events.append(event)
            elif event.type in PLAYBACK_HELD_EVENT_TYPES:
                self.held_live_events.append(event)
            elif self.exit_on_input and event.type in PLAYBACK_EXIT_EVENT_TYPES:
                self.exit_requested = True
                self._note_end(reason='exit_input')
        return internal_events, quit_events

    def frame_seconds(self: Self, *, measured: float) -> float:
        """Return the recording's dt, after asking the installed doors as always.

        Returns:
            Seconds (past the recording's end, the installed doors' answer).

        """
        return self.replay.frame_seconds(measured=self.base.frame_seconds(measured=measured))

    def performance_frame_seconds(self: Self, *, measured: float, frame_seconds: float) -> float:
        """Return the installed doors' frame time for FPS events and the statistics.

        Returns:
            Seconds.

        """
        return self.base.performance_frame_seconds(measured=measured, frame_seconds=frame_seconds)

    def paced_frame_seconds(self: Self) -> float | None:
        """Return how the installed doors pace the frame (a demo plays at the game's speed).

        Returns:
            Seconds, or None for the target FPS.

        """
        return self.base.paced_frame_seconds()

    def hold_frame(self: Self) -> bool:
        """Return whether the installed doors hold the frame.

        Returns:
            True to run no frame now.

        """
        return self.base.hold_frame()

    def draw_overlay(self: Self, *, surface: pygame.Surface) -> None:
        """Let the installed doors draw their overlay."""
        self.base.draw_overlay(surface=surface)

    def input_snapshot(self: Self) -> InputSnapshot:
        """Read the installed doors' snapshot (a recording keeps it), then serve the replay's.

        Returns:
            The recording's polled input for this frame.

        """
        self.last_base_snapshot = self.base.input_snapshot()
        return self.replay.input_snapshot()

    def devices(self: Self) -> DeviceRegistry:
        """Return the replay's registry of recorded devices.

        Returns:
            The registry.

        """
        return self.replay.devices()

    def saves(self: Self, *, namespace: str) -> SaveManager:
        """Return the replay's sandboxed store for ``namespace``.

        Returns:
            A memory store: real saves are never touched.

        """
        return self.replay.saves(namespace=namespace)

    def wall_clock_time(self: Self) -> datetime:
        """Return the recording's wall clock.

        Returns:
            Timezone-aware UTC time.

        """
        return self.replay.wall_clock_time()

    def control_events_for_frame(self: Self, *, frame_number: int) -> list[ControlEvent]:
        """Return the recording's control events to apply again on its current frame.

        Returns:
            The control events.

        """
        return self.replay.control_events_for_frame(frame_number=frame_number)

    def end_frame(
        self: Self,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
    ) -> None:
        """Compare the frame with the recording, then let the installed doors end it (rule 5).

        The scene manager calls the two halves itself (``compare_frame``, then the installed
        doors' ``end_frame``), so only the comparison's errors end the scope; this is the
        EngineSources door for any other caller. The installed doors end the frame even when
        the comparison raises.
        """
        try:
            self.compare_frame(
                frame_number=frame_number, dt=dt, scene=scene, control_events=control_events
            )
        finally:
            self.base.end_frame(
                frame_number=frame_number, dt=dt, scene=scene, control_events=control_events
            )

    def compare_frame(
        self: Self,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
    ) -> None:
        """Compare the frame with the recording (the scope's half of ``end_frame``; rule 5).

        The scope's own ``playback`` marker is left out: it belongs to the session, not to the
        recording played.
        """
        self.replay.end_frame(
            frame_number=frame_number,
            dt=dt,
            scene=scene,
            control_events=[
                control_event
                for control_event in control_events
                if control_event.kind != PLAYBACK_KIND
            ],
        )
        self.frames_played += 1
        if self.replay.stop_requested:
            replay_end_reason = self.replay.result.end_reason
            if replay_end_reason == 'diverged':
                self._note_end(reason='diverged')
            elif replay_end_reason == 'truncated':
                self._note_end(reason='truncated')
            else:
                self._note_end(reason='end_of_recording')


class PlaybackRequest(BaseModel):
    """A playback scope to enter at the start of the next frame (read-only; rule 1).

    Attributes:
        sources: The scoped doors the playback runs on.
        start: The start of the scene to rebuild (the ``scene_start`` the first played frame
            holds).
        scene_class: The class ``start.scene_class`` names.
        then: The scene to make active when the scope ends.
        kind: What the scope plays.
        frame_count: How many recorded frames the scope plays at most (from its first played
            frame to the recording's end); the ``playback`` control event's ``frames``.
        first_logic_frame: ``start.first_logic_frame``: the state the first played frame
            began in (glitchygames/scene_start.py, rule 7).

    """

    # Live objects (doors, scenes) are held as they are, never copied or validated deeply
    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    sources: PlaybackSources
    start: SceneStart
    scene_class: type[Scene]
    then: Scene
    kind: PlaybackKind
    frame_count: int
    first_logic_frame: FirstLogicFrame

    def begin_session(
        self: Self, *, live_scene: Scene, fps_event_seconds: float
    ) -> PlaybackSession:
        """Save what the scope's end restores, as the scope begins (rule 2).

        Args:
            live_scene: The active scene, stashed for the scope.
            fps_event_seconds: When the live game last posted an FPS event.

        Returns:
            The session, holding the random streams and frame clock as they are now.

        """
        return PlaybackSession(
            sources=self.sources,
            live_scene=live_scene,
            then=self.then,
            kind=self.kind,
            saved_random_states=capture_stream_states(),
            saved_frame_clock_seconds=frame_clock_seconds(),
            saved_fps_event_seconds=fps_event_seconds,
        )


class PlaybackSession(BaseModel):
    """A playback scope in progress: what it runs on and what its end restores (read-only).

    Attributes:
        sources: The scoped doors pushed for the scope.
        live_scene: The scene that was active when the scope began, stashed without
            ``cleanup()`` and never touched while the scope runs.
        then: The scene to make active when the scope ends.
        kind: What the scope plays.
        saved_random_states: ``capture_stream_states()`` as the scope began.
        saved_frame_clock_seconds: The frame clock as the scope began.
        saved_fps_event_seconds: When the live game last posted an FPS event
            (``SceneManager._previous_fps_event_seconds``), on the live frame clock.

    """

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    sources: PlaybackSources
    live_scene: Scene
    then: Scene
    kind: PlaybackKind
    saved_random_states: dict[str, Any]
    saved_frame_clock_seconds: float
    saved_fps_event_seconds: float

    def outcome(self: Self, *, reason: PlaybackEndReason) -> PlaybackOutcome:
        """Return how the scope ended (rule 4).

        Args:
            reason: Why it ended.

        Returns:
            The outcome.

        """
        return PlaybackOutcome(
            kind=self.kind, reason=reason, frames_played=self.sources.frames_played
        )


class PlaybackOutcome(BaseModel):
    """How a playback scope ended (``SceneManager.last_playback_outcome``; rule 4).

    Attributes:
        kind: What the scope played.
        reason: Why it ended: ``'exit_input'`` (the player's press), ``'recording_quit'`` (the
            recording asked to quit), ``'end_of_recording'``, ``'truncated'`` (a cut-off file's
            last complete frame), ``'diverged'``, ``'error'`` (an error in the scope, logged)
            or ``'quit'`` (the run ended during the scope).
        frames_played: How many frames the scope compared with the recording.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    kind: PlaybackKind
    reason: PlaybackEndReason
    frames_played: int


def find_scene_class(*, name: str) -> type[Scene] | None:
    """Return the loaded ``Scene`` subclass named ``name`` (rule 1).

    Args:
        name: A class name (``SceneStart.scene_class``).

    Returns:
        The class, or None when no loaded subclass has the name or several do (logged).

    """
    matches: list[type[Scene]] = []
    seen: set[type[Scene]] = set()
    unvisited: collections.deque[type[Scene]] = collections.deque([Scene])
    while unvisited:
        scene_class = unvisited.popleft()
        for subclass in scene_class.__subclasses__():
            if subclass not in seen:
                seen.add(subclass)
                unvisited.append(subclass)
                if subclass.__name__ == name:
                    matches.append(subclass)
    if len(matches) > 1:
        LOG.warning('Several scene classes are named %s; which to rebuild is unknown', name)
        return None
    return matches[0] if matches else None


def _playable_start(
    *, frames: Sequence[dict[str, Any]], options: PlaybackOptions
) -> SceneStart | None:
    """Return the scene start a playback can begin at, from ``options.start_frame`` (rule 1).

    Args:
        frames: The recording's decoded frames.
        options: How the scope plays.

    Returns:
        The start, or None (logged) when the frame does not exist, holds no scene start, an
        unreadable one, or one without its first logic frame (glitchygames/scene_start.py,
        rule 7: it cannot be aligned).

    """
    kind = options.kind
    start_frame = options.start_frame
    if start_frame >= len(frames):
        LOG.warning('No %s: the recording has no frame %d', kind, start_frame)
        return None
    start_record = frames[start_frame].get(SCENE_START_FIELD)
    if start_record is None:
        LOG.warning('No %s: frame %d of the recording holds no scene start', kind, start_frame)
        return None
    try:
        start = SceneStart.from_json(start_record)
    except ValidationError as error:
        LOG.warning('No %s: frame %d holds an unusable scene start: %s', kind, start_frame, error)
        return None
    if start.first_logic_frame is None:
        LOG.warning(
            'No %s: the scene start at frame %d cannot be aligned (no first logic frame)',
            kind,
            start_frame,
        )
        return None
    return start


def start_playback(
    *,
    manager: SceneManager,
    header: dict[str, Any],
    frames: Sequence[dict[str, Any]],
    then: Scene,
    options: PlaybackOptions = DEFAULT_PLAYBACK_OPTIONS,
) -> bool:
    """Play a recording held in memory in a playback scope (rule 1).

    Args:
        manager: The running scene manager.
        header: The recording's header fields (``random_seed`` and ``recorded_at`` required).
        frames: Its decoded frames.
        then: The scene to make active when the scope ends (usually the live scene).
        options: How the scope plays (from ``options.start_frame``).

    Returns:
        True when the scope will begin at the start of the next frame; False (logged) when the
        frame holds no usable scene start, its scene class is not found, the header cannot be
        replayed, or a scope is already starting or playing.

    """
    kind = options.kind
    start_frame = options.start_frame
    start = _playable_start(frames=frames, options=options)
    if start is None or start.first_logic_frame is None:
        return False
    scene_class = find_scene_class(name=start.scene_class)
    if scene_class is None:
        LOG.warning('No %s: no scene class named %s is loaded', kind, start.scene_class)
        return False
    try:
        replay = playback_replay_sources(
            header=header, frames=frames, start=start, start_frame=start_frame
        )
    except TraceFormatError as error:
        LOG.warning('No %s: the recording cannot be replayed: %s', kind, error)
        return False
    return manager.request_playback(
        request=PlaybackRequest(
            sources=PlaybackSources(
                base=active_sources(), replay=replay, exit_on_input=options.exit_on_input
            ),
            start=start,
            scene_class=scene_class,
            then=then,
            kind=kind,
            frame_count=len(frames) - start_frame,
            first_logic_frame=start.first_logic_frame,
        )
    )


def start_playback_from_recording(
    *,
    manager: SceneManager,
    path: Path,
    then: Scene,
    options: PlaybackOptions = DEFAULT_PLAYBACK_OPTIONS,
) -> bool:
    """Play a recording file in a playback scope (``start_playback``).

    A file cut off part way plays up to its last complete frame.

    Args:
        manager: The running scene manager.
        path: The recording.
        then: The scene to make active when the scope ends.
        options: How the scope plays.

    Returns:
        As ``start_playback``; also False (logged) for a missing or unreadable file.

    """
    try:
        read_result = read_trace_result(path=path)
    except (OSError, TraceFormatError) as error:
        LOG.warning('No %s: %s cannot be read: %s', options.kind, path, error)
        return False
    header = {name: value for name, value in read_result.trace.items() if name != FRAMES_FIELD}
    return start_playback(
        manager=manager,
        header=header,
        frames=read_result.trace[FRAMES_FIELD],
        then=then,
        options=options,
    )
