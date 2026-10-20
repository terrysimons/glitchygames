"""In-game playback: a running game plays a recording to a rebuilt scene, then goes on.

Demos and instant replays run inside a playback scope, not a new engine run
(plans/2026-10-19-gameplay-replay.md, section 5.2). The rules:

1. Starting (``start_playback``; ``start_playback_from_recording`` reads a file first): the
   frame played first must hold a ``scene_start`` (glitchygames/scene_start.py) whose scene
   class is found among the loaded ``Scene`` subclasses by name; otherwise nothing starts
   (logged; False). The replay sources are made (``playback_replay_sources``, rule 18 of
   glitchygames/replay/driver.py) and the scope is requested (``SceneManager.
   request_playback``): the scene manager enters it at the start of the next frame, so the
   rebuilt scene's first frame is a whole frame, as recorded, and the frame that asked ends on
   the live doors. Scopes do not nest.
2. Entering (``SceneManager._enter_playback``): the random streams, the frame clock and the FPS
   event timer are saved; the live scene is stashed without ``cleanup()``; ``PlaybackSources``
   are pushed on top of the installed doors (``push_scoped_sources``; glitchygames/sources.py);
   a ``playback`` control event is recorded (a marker: replaying the session starts the scope
   again from the recorded input, so it is compared, never applied again); the scene is rebuilt
   (``rebuild_scene``, which sets the streams and frame clock it began with) and made active
   as a switch would, and the frame takes the recording's first dt. The FPS event timer starts
   on the rebuilt frame clock, as ``SceneManager.start`` starts it, so a recording whose scene
   began with the run (frame 0) posts its FPS events again exactly.
3. Frames: ``PlaybackSources`` serve the recording to the scene (rule 4) and the scene
   manager runs every frame as always, paced and presented by the installed doors (a demo
   plays at the game's speed).
4. Ending: after each frame's ``end_frame``, the scope ends when the player asked to leave
   (``exit_on_input``: any key or button, ``PLAYBACK_EXIT_EVENT_TYPES``), or the recording
   ended or diverged (the replay stops there; a playback never pauses). An error in a frame
   or while entering ends it too, logged (``SceneManager._run_frame`` contains it). Ending
   (``SceneManager._exit_playback``) keeps the replay's result
   (``SceneManager.last_playback_result``; a scope left early keeps the end reason
   ``'running'``), cleans up the playback's scene, pops the scoped doors and restores the
   streams, the frame clock and the FPS event timer, then makes the live scene active again
   exactly as it was (no ``setup()`` again: only its snap mode, event proxies, caption and a
   full redraw), or switches to ``then`` when that is another scene.
5. The scoped doors (``PlaybackSources``):

   - ``pump_events``: the installed doors pump once per pump of the frame (the real queue live;
     the session's recorded batch when the session is replayed, so the exit press replays
     too). Their events are sorted with the internal-post tracker: external events (the
     player's input, device and window events) reach only the exit check, never the scene;
     the window's QUIT is kept (it still quits the game); internal events, the playback
     scene's own posts, go to the replay (``ReplaySources.pump_events(real_events=...)``),
     which matches them with the recorded ones. The first pump drops internal events posted
     before the scope began (the live game's last FPS event, say): they belong to the live
     game, which is not running, and would be divergences of the recording's first frame (a
     QUIT the live game posted is kept). The batch is the replay's (recorded external events,
     matched internal ones), then the QUIT.
   - ``input_snapshot``: the installed doors' snapshot is read (a recording of the session
     records the player's polled input), the replay's is returned.
   - ``frame_seconds``: the replay's (the recording's dt; past its end, the installed doors'
     measurement), asked after the installed doors were asked as always.
   - ``saves``, ``devices``, ``wall_clock_time``, ``control_events_for_frame``,
     ``random_seed``, ``opened_save_namespaces``: the replay's (saves are a sandbox seeded
     from the scene start's save view: real saves are never touched).
   - ``end_frame``: the replay compares the frame (its ``playback`` marker left out: the
     recording never holds it), then the installed doors end it (a recording of the session
     writes it; glitchygames/recording.py, Playback scopes).
   - ``captures_scene_starts`` is True; ``stop_requested``, pacing, holding, presenting and
     the overlay are the installed doors' (the scope never stops the run).

Limits: a scene must be rebuildable from its start (``Scene.replay_arguments``). A scene that
began on a later frame of a recording (``start_frame``) is rebuilt and set up before that
frame's logic runs: exact for a scene set up between frames (a recording's frame 0, or a
switch made between frames), while a scene switched to inside its first frame (the usual
``next_scene`` switch, at the frame's end) did not run that frame's logic when recorded, so
its playback diverges there. The player's device and window events during a scope never reach
the live game (a controller plugged in during a demo is not seen).
"""

from __future__ import annotations

import collections
import logging
from typing import TYPE_CHECKING, Any, Final, Self

import pygame
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from glitchygames.playback_scope import DEMO_PLAYBACK, PlaybackKind, PlaybackRequest
from glitchygames.recording import (
    INTERNAL_ORIGIN,
    SCENE_START_FIELD,
    event_origin,
    pending_internal_posts,
    take_internal_post,
)
from glitchygames.replay.driver import playback_replay_sources
from glitchygames.scene_start import SceneStart
from glitchygames.scenes import Scene
from glitchygames.sources import active_sources
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

# The player's presses that end a playback started with exit_on_input (spec 5.2: any key or
# button)
PLAYBACK_EXIT_EVENT_TYPES: Final = frozenset({
    pygame.KEYDOWN,
    pygame.MOUSEBUTTONDOWN,
    pygame.JOYBUTTONDOWN,
    pygame.CONTROLLERBUTTONDOWN,
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
        captures_scene_starts: True: scenes built inside the scope capture their starts.
        random_seed: The recording's master seed.

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
        # The EngineSources property, as a plain attribute: set once, for the whole scope
        self.captures_scene_starts = True
        self.random_seed = replay.random_seed
        # Posts the live game made that no pump has returned yet as the scope began (rule 5)
        self._posts_before_scope: list[tuple[int, dict[str, Any]]] = []
        self._has_pumped = False

    @property
    def ended(self: Self) -> bool:
        """True once the replay stopped: the recording ended or diverged."""
        return self.replay.stop_requested

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
        """Note the live game's pending posts, then let the replay own the post tracker."""
        self._posts_before_scope = list(pending_internal_posts())
        self._has_pumped = False
        self.replay.on_installed()

    def on_uninstalled(self: Self) -> None:
        """Let the replay give up the post tracker."""
        self.replay.on_uninstalled()

    def pump_events(self: Self) -> list[pygame.event.Event]:
        """Pump the installed doors once; serve the replay's batch plus the window's QUIT (rule 5).

        Returns:
            The replay's batch in its recorded order, then any QUIT the installed doors read.

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
        return [*self.replay.pump_events(real_events=internal_events), *quit_events]

    def _sort_base_events(
        self: Self,
        *,
        base_events: list[pygame.event.Event],
        live_posts: list[tuple[int, dict[str, Any]]],
        scope_posts: list[tuple[int, dict[str, Any]]],
        is_first_pump: bool,
    ) -> tuple[list[pygame.event.Event], list[pygame.event.Event]]:
        """Sort the installed doors' batch for the replay, the game and the exit check (rule 5).

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
        dropped_event_count = 0
        for event in base_events:
            if take_internal_post(event=event, pending=live_posts):
                # The live game's own: dropped, but its quit request still quits the game
                if event.type == pygame.QUIT:
                    quit_events.append(event)
                else:
                    dropped_event_count += 1
            elif take_internal_post(event=event, pending=scope_posts):
                internal_events.append(event)
            elif event_origin(event=event, pending=[]) == INTERNAL_ORIGIN:
                # Internal by type alone: on the first pump, posted before the scope began
                if is_first_pump:
                    dropped_event_count += 1
                else:
                    internal_events.append(event)
            elif event.type == pygame.QUIT:
                quit_events.append(event)
            elif self.exit_on_input and event.type in PLAYBACK_EXIT_EVENT_TYPES:
                self.exit_requested = True
        if dropped_event_count:
            LOG.debug(
                'Dropped %d events the live game posted before the playback', dropped_event_count
            )
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
        self.base.input_snapshot()
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

        The installed doors end it even when the comparison raises.
        """
        try:
            self.replay.end_frame(
                frame_number=frame_number,
                dt=dt,
                scene=scene,
                # The scope's own marker belongs to the session, not to the recording played
                control_events=[
                    control_event
                    for control_event in control_events
                    if control_event.kind != PLAYBACK_KIND
                ],
            )
        finally:
            self.base.end_frame(
                frame_number=frame_number, dt=dt, scene=scene, control_events=control_events
            )


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
    if start_frame >= len(frames):
        LOG.warning('No %s: the recording has no frame %d', kind, start_frame)
        return False
    start_record = frames[start_frame].get(SCENE_START_FIELD)
    if start_record is None:
        LOG.warning('No %s: frame %d of the recording holds no scene start', kind, start_frame)
        return False
    try:
        start = SceneStart.from_json(start_record)
    except ValidationError as error:
        LOG.warning('No %s: frame %d holds an unusable scene start: %s', kind, start_frame, error)
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
