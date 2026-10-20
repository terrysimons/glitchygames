"""In-game playback: a running game plays a recording to a rebuilt scene, then goes on.

Demos and instant replays run inside a playback scope, not a new engine run
(plans/2026-10-19-gameplay-replay.md, section 5.2). The rules:

1. Starting (``start_playback``; ``start_playback_from_recording`` reads a file first): the
   frame played first (``PlaybackOptions.start_frame``) must hold a ``scene_start``
   (glitchygames/scene_start.py) with its first logic frame (rule 7 there: a recording writes
   a start on the scene's first logic frame, so the start's frame is where its logic began),
   and its scene class must be found among the loaded ``Scene`` subclasses (``find_scene_class``:
   by module and qualified name, else, where the modules cannot be compared (none recorded, or
   ``__main__`` on either side), by a name no other such scene shares); otherwise
   nothing starts (logged; False), as for a recording that cannot be replayed (a malformed one
   included). The replay sources are made (``playback_replay_sources``, rule 18 of
   glitchygames/replay/driver.py) and the scope is requested (``SceneManager.
   request_playback``): the scene manager enters it at the start of the next frame, so the
   rebuilt scene's first frame is a whole frame, as recorded, and the frame that asked ends on
   the live doors. A request made while a transition plays waits for its end. A request made
   in a frame whose end switches scenes (``next_scene``) is dropped, logged: the scene to
   return to has gone. Scopes do not nest: inside a scope, a request is answered with the
   answer the frame being played recorded (an instant-replay journal's ``playback_answers``)
   and requests nothing, or, without one, refused (``answered_playback_request``;
   glitchygames/instant_replay.py, rule 8).
2. Entering (``SceneManager._enter_playback``): the random streams, the frame clock, the FPS
   event timer and the scene manager's ``previous_scene`` are saved
   (``PlaybackRequest.begin_session``); the live scene is stashed without ``cleanup()``;
   ``PlaybackSources`` are pushed on top of the installed doors
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
   plays at the game's speed), but for the fast-forwarded frames (rule 6).
4. Ending: after each frame, the scope ends when its doors found a reason
   (``PlaybackSources.end_reason``): the player's press (``exit_on_input``: any key or button,
   ``PLAYBACK_EXIT_EVENT_TYPES``), the recording's quit (its window's QUIT or the playback
   scene's own ``quit_game()``: the scope ends, the game does not quit), the game's request
   (``SceneManager.end_playback``, ``'ended_by_game'``: from a supervisor, the scope ends once
   that frame ended; between frames, at once; from the played scene's own code, ignored, as
   its original call did nothing), or the recording's end or divergence (the
   replay stops there; a playback never pauses). An error in the scope's
   part of a frame (its frame, the comparison, or entering) ends it too, logged
   (``SceneManager._run_frame`` contains it); an error of the installed doors (a session
   recorder that cannot write) propagates as it would outside a scope. The run's end
   (``SceneManager.terminate``, after the player's QUIT) ends a scope in progress first and
   drops a requested one, so the live scene is the one torn down. Ending
   (``SceneManager._exit_playback``) keeps the replay's result
   (``SceneManager.last_playback_result``) and a ``PlaybackOutcome``
   (``SceneManager.last_playback_outcome``: the kind, the reason and the frames played), cleans
   up the playback's scene, removes every supervisor and control event handler the scope's
   code added while it played (the rebuilt scene's setup(), event handlers or cleanup() may add
   one, a ghost recorder say: ``SceneManager.add_supervisor`` gives it to the scope; those
   added before the scope began, or by the live game's own supervisors and handlers while it
   played, stay; ``SceneManager.in_playback_scope``, true while the scoped doors are pushed,
   is the one answer to "is a scope playing"), pops the
   scoped doors, restores the streams, the frame clock, the
   FPS event timer, the scene manager's ``previous_scene``, its rumble controller (rule 8) and
   the live polled input (the installed doors' latest snapshot), posts again the live game's
   posts the scope drained and hands back the player's held events (rule 5), drops the
   playback scene's own posts still queued (made after its frame's last pump: in
   ``update()``, an event handler, a supervisor, its cleanup; ``sources.discard_scope_posts``:
   they stop being pending posts, and the live doors' next read of SDL's queue loses them
   before a recording, the instant-replay journal or the game sees the batch; a replay of the
   session drops them the same way as its playback scene posts them again), then makes the
   live scene active again
   exactly as it was (no ``setup()`` again: only its snap mode, event proxies, caption and a
   full redraw), or switches to ``then`` when that is another scene. The frame that ends the
   scope still finishes afterwards, so the restored live frame clock resumes one frame later
   (it advances by that frame's dt).
5. The scoped doors (``PlaybackSources``):

   - ``pump_events``: the installed doors pump once per pump of the frame (the real queue live;
     the session's recorded batch when the session is replayed, so the exit press replays
     too). Their batch is sorted with the internal-post tracker. The player's QUIT (and one the
     live game posted) is kept: it quits the game. Internal events, the playback scene's own
     posts, go to the replay (``ReplaySources.pump_events(real_events=...)``), which matches
     them with the recorded ones. Internal events posted before the scope began (the live
     game's last FPS event, say: they are the live game's, and would be divergences of the
     recording's first frame) are held, as are the external events the live game must not
     lose (releases, device and window events, ``PLAYBACK_HELD_EVENT_TYPES``): one list
     (``held_live_events``), in the order they were pumped, each with its origin, delivered in
     that order before the first pump after the scope (``sources.redeliver_events``; a
     recording writes them into that frame's ``redelivered_events``). Events still waiting to
     be redelivered when a scope begins (a demo that ended into a scene starting the next
     one) are taken into the new scope's list first, so they reach the live game, never a
     playback scene. When the run ends during a scope (``terminate``) they are dropped: no
     frame follows to deliver them. External events reach only the exit check, never the
     scene; presses and motion are dropped. The batch is the
     replay's (recorded external events, matched internal ones) without any QUIT (a QUIT in
     it ends the scope: ``recording_quit``), then the kept QUIT.
   - ``input_snapshot``: the installed doors' snapshot is read (a recording of the session
     records the player's polled input; it is kept as ``last_base_snapshot``), the replay's is
     returned.
   - ``frame_seconds``: the replay's (the recording's dt; past its end, the installed doors'
     measurement), asked after the installed doors were asked as always.
   - ``saves``, ``devices``, ``wall_clock_time``, ``random_seed``,
     ``opened_save_namespaces``: the replay's (saves are a sandbox seeded from the scene
     start's save view: real saves are never touched).
   - ``control_events_for_frame``: the installed doors' (a replay of the session re-applies
     its breakpoints on the scope's frames too); the played recording's re-applied control
     events are never applied again (they were applied in the session that recorded them) and
     never compared (glitchygames/replay/driver.py, rule 8).
   - ``end_frame`` is ``compare_frame`` (the replay compares the frame, its ``playback``
     marker left out: the recording never holds it), then the installed doors' ``end_frame``
     (a recording of the session writes it; glitchygames/recording.py, Playback scopes). The
     scene manager calls the two itself, so only the comparison's errors end the scope.
   - ``captures_scene_starts`` is True; ``stop_requested``, pacing, holding, presenting and
     the overlay are the installed doors' (the scope never stops the run), except while
     fast-forwarding (rule 6).
6. Fast-forward (``PlaybackOptions.fast_forward_frames``): the scope's first N frames run in
   full but unseen and unheard. While ``PlaybackSources.is_fast_forwarding`` (fewer frames
   compared than N), ``presents_frames`` is False and ``paced_frame_seconds()`` is 0.0, the
   doors a headless replay uses (the scene manager neither presents nor waits; the next
   presented frame updates the whole display), and after each such frame every sound it
   started is stopped and music is paused (``FrameSilencer``, glitchygames/replay/silence.py,
   the code path a restarted replay's rebuild uses; it follows the game's own music pauses from
   the scope's start, and the live game's sounds playing then play on, live voices aside).
   After the Nth frame the silence ends
   (music the silencer paused plays on, unless the game paused it) and the frames play as rule
   3 says, heard as the game plays them; so does a scope that ends during the fast-forward.
   Music is the one mixer's: the scope neither saves nor restores it, so music the playback's
   scene starts or stops is the live game's too. The scope's first frame is paced as the live
   doors pace it (the loop asks before the frame enters the scope). None of this changes what
   a frame does, so a recording or replay of the session (watched or headless) is unchanged.
7. Instant replay (``SceneManager.instant_replay``, ``start_instant_replay``): the active
   scene's instant-replay journal (glitchygames/instant_replay.py) plays in a scope of kind
   ``'instant'`` from its ``start_frame``, returning to the scene shown (the journal's scene,
   or the pause screen presenting it), with no exit on input: the player's presses reach
   nothing, and the game decides when it ends (the journal's end, or
   ``SceneManager.end_playback`` from a supervisor, which reads the player's polled input from
   ``SceneManager.playback_player_input``). The frames before the last
   ``Scene.INSTANT_REPLAY_SECONDS`` of frame time are fast-forwarded
   (``fast_forward_frame_count``); the rest are shown at the game's pace. Frame time, not
   game time: the shown part takes that long to watch, a paused stretch in it included.
   Refused (False, nothing starts) when the scene keeps no journal (it does not offer instant
   replay, its first logic frame has not run, or a scope plays) or
   the journal holds more frame time than ``Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS``.
   The request is answered as any playback request is (rule 1: a playback of the journal gets
   the recorded answer and requests nothing), so a scene that asks after every goal plays back
   across its earlier replays. The journal's recording is taken as the request is made: the
   frame that asks is not in it (it ends live, before the scope begins).
8. Rumble and live voices: a playback never rumbles the player's real controllers, neither
   while fast-forwarding nor in the frames it shows (a demo's crash buzzing the player's hands
   would be the playback's, not the game's). While a scope plays, ``SceneManager.rumble`` is a
   rumble controller of its own (the playback scene's pulses, sustained levels and shakes go
   there and reach no device); the live game's controller waits untouched and is back when the
   scope ends, so a playback's pulse never carries into live play. The live scene's synth
   voices (and those of the scene the scope returns to) pause behind the scope and play on
   after it (``LiveAudio.update``'s ``paused_owners``); the playback scene's own voices end
   with it.

Limits: a scope that fast-forwards inside a restarted replay's rebuild silences on top of the
rebuild's silence: the end of its fast-forward may resume music during the rebuild (which
pauses it again after the next frame). A scene must be rebuildable from its start
(``Scene.replay_arguments``). Of a scene
that arrived by a transition, the arrival step is repeated, but the events the ride delivered
to it (releases, window and device events) are not: a scene they change diverges. The
first logic frame's earlier posts are counted from the internal-post tracker, so they are
exact while posts are tracked (while recording or replaying, and from the first setup of a
scene that keeps an instant-replay journal: glitchygames/instant_replay.py, whose
``JournalRecording`` a scope plays from its ``start_frame``). A ``--record-trace`` recording
of a session that played a scope cannot itself be played in-game from a frame inside or after
that scope: a recorder writes no ``playback_answers`` or ``resume_bridge`` (only an
instant-replay journal does), so its scene's playback requests and its resumption after the
scope are not known (it replays exactly with ``--replay-trace``, which runs the scope again).
Rumble in joystick mode asks the devices door for the joysticks (glitchygames/input/rumble.py);
inside a scope it asks nothing (rule 8), so when the played recording's joystick count changed
part way, a later device enumeration by the played scene may read an earlier recorded answer.
"""

from __future__ import annotations

import collections
import logging
from fractions import Fraction
from typing import TYPE_CHECKING, Any, Final, Literal, Self

import pygame
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from glitchygames.events import AUDIO_EVENTS, WINDOW_EVENTS
from glitchygames.input.state import current_input
from glitchygames.randomness import capture_stream_states
from glitchygames.recording import (
    DT_FIELD,
    EXTERNAL_ORIGIN,
    INTERNAL_ORIGIN,
    SCENE_START_FIELD,
    event_origin,
    pending_internal_posts,
    take_internal_post,
)
from glitchygames.replay.driver import (
    SCRIPT_MODULE_NAME,
    SOURCE_TRUNCATED_HEADER_FIELD,
    is_cut_off,
    playback_replay_sources,
)
from glitchygames.replay.silence import FrameSilencer
from glitchygames.scene_start import FirstLogicFrame, SceneStart
from glitchygames.scenes import Scene
from glitchygames.sources import active_sources, frame_clock_seconds
from glitchygames.supervision import PLAYBACK_KIND
from glitchygames.tracing import FRAMES_FIELD, TraceFormatError, read_trace_result

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from datetime import datetime
    from pathlib import Path

    from glitchygames.input.devices import DeviceRegistry
    from glitchygames.input.state import InputSnapshot
    from glitchygames.replay.driver import ReplaySources
    from glitchygames.scenes import SceneManager
    from glitchygames.sources import EngineSources, RedeliveredEvent
    from glitchygames.state.manager import SaveManager
    from glitchygames.supervision import ControlEvent

LOG = logging.getLogger('game.replay.playback')

# What a scope plays: an attract-mode demo, or an instant replay of the live scene
type PlaybackKind = Literal['demo', 'instant']
DEMO_PLAYBACK: Final = 'demo'
INSTANT_PLAYBACK: Final = 'instant'
# Why a scope ended (PlaybackOutcome.reason)
type PlaybackEndReason = Literal[
    'exit_input',
    'recording_quit',
    'end_of_recording',
    'truncated',
    'diverged',
    'error',
    'quit',
    'ended_by_game',
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
        fast_forward_frames: How many frames, from ``start_frame``, run unpresented, unpaced
            and silent before the rest play as usual (rule 6; an instant replay's
            ``fast_forward_frame_count``).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    exit_on_input: bool = False
    kind: PlaybackKind = DEMO_PLAYBACK
    start_frame: int = Field(default=0, ge=0)
    fast_forward_frames: int = Field(default=0, ge=0)


# A playback with no options: no exit on input, a demo, from the recording's first frame
DEFAULT_PLAYBACK_OPTIONS = PlaybackOptions()


class PlaybackSources:
    """A playback scope's doors (implements glitchygames.sources.EngineSources; rule 5).

    Attributes:
        base: The installed doors underneath (live, recording or a replay of the session).
        replay: The replay serving the recording to the playback's scene.
        exit_on_input: True when any key or button press ends the scope.
        fast_forward_frames: How many of the scope's first frames run unpresented, unpaced and
            silent (rule 6).
        is_fast_forwarding: True while the frame running (or about to run) is one of them:
            fewer frames compared than ``fast_forward_frames``.
        exit_requested: True once such a press arrived.
        recording_quit: True once the recording asked to quit (its window's QUIT, or the
            playback scene's own ``quit_game()``): the scope ends, the game does not quit.
        captures_scene_starts: True: scenes built inside the scope capture their starts.
        random_seed: The recording's master seed.
        frames_played: How many frames the replay compared so far.
        end_reason: Why the scope should end now, or None while it plays on: the first found
            of the player's exit press (``'exit_input'``) and the recording's quit
            (``'recording_quit'``), found by the frame's pumps, the game's request
            (``'ended_by_game'``, set by ``SceneManager.end_playback``), then the replay's end
            (``'end_of_recording'``, ``'truncated'`` or ``'diverged'``), found by
            ``compare_frame``.
        last_base_snapshot: The installed doors' latest polled input (the live input as the
            scope began, then each frame's): the live game's input when the scope ends.
        held_live_events: The live game's events the scope's pumps drained and held, each
            with its origin, in pump order: its own posts made before the scope (internal) and
            the player's releases, device and window events (external,
            ``PLAYBACK_HELD_EVENT_TYPES``). Delivered before the first pump after the scope.
        live_posts_before_scope: The live game's posts no pump had returned yet as the scope
            began (its first pump holds them; rule 5).
        has_pumped: True once the scope's doors pumped: from then on every post still pending
            is the scope's own (``SceneManager._exit_playback`` drops those as it ends).

    """

    def __init__(
        self: Self,
        *,
        base: EngineSources,
        replay: ReplaySources,
        exit_on_input: bool,
        fast_forward_frames: int = 0,
    ) -> None:
        """Wrap the installed doors and a replay.

        Args:
            base: The installed doors.
            replay: The replay sources (``playback_replay_sources``).
            exit_on_input: True to end the scope at any key or button press.
            fast_forward_frames: How many of the scope's first frames to fast-forward (rule 6).

        """
        self.base = base
        self.replay = replay
        self.exit_on_input = exit_on_input
        self.fast_forward_frames = fast_forward_frames
        # A plain attribute, kept by compare_frame (the class has as many methods as it may)
        self.is_fast_forwarding = fast_forward_frames > 0
        # Keeps the fast-forwarded frames silent (the rebuild's code path); the live game's
        # sounds playing as the scope began play on
        self._silencer = FrameSilencer(spares_playing_sounds=True)
        self.exit_requested = False
        self.recording_quit = False
        # The EngineSources property, as a plain attribute: set once, for the whole scope
        self.captures_scene_starts = True
        self.random_seed = replay.random_seed
        self.frames_played = 0
        self.end_reason: PlaybackEndReason | None = None
        self.last_base_snapshot: InputSnapshot = current_input()
        self.held_live_events: list[RedeliveredEvent] = []
        self.live_posts_before_scope: list[tuple[int, dict[str, Any]]] = []
        self.has_pumped = False

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
        """Whether the frame is presented: never while fast-forwarding, else as the doors do."""
        return not self.is_fast_forwarding and self.base.presents_frames

    @property
    def draws_overlay(self: Self) -> bool:
        """Whether the installed doors draw an overlay of their own."""
        return self.base.draws_overlay

    def on_installed(self: Self) -> None:
        """Note the live game's pending posts and input, then let the replay own the tracker.

        A scope that fast-forwards follows the game's music controls from here (rule 6), so
        the rebuilt scene's own are followed too.
        """
        self.live_posts_before_scope = list(pending_internal_posts())
        self.has_pumped = False
        self.last_base_snapshot = current_input()
        if self.is_fast_forwarding:
            self._silencer.begin()
        self.replay.on_installed()

    def on_uninstalled(self: Self) -> None:
        """Let the replay give up the post tracker; end a fast-forward's silence (rule 6)."""
        self._silencer.finish()
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
        is_first_pump = not self.has_pumped
        self.has_pumped = True
        live_post_count = len(self.live_posts_before_scope) if is_first_pump else 0
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

        Holds the live game's posts and the events it must not lose (``held_live_events``).

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
                self.held_live_events.append((event, INTERNAL_ORIGIN))
            elif take_internal_post(event=event, pending=scope_posts):
                internal_events.append(event)
            elif event_origin(event=event, pending=[]) == INTERNAL_ORIGIN:
                # Internal by type alone: on the first pump, posted before the scope began
                if is_first_pump:
                    self.held_live_events.append((event, INTERNAL_ORIGIN))
                else:
                    internal_events.append(event)
            elif event.type in PLAYBACK_HELD_EVENT_TYPES:
                self.held_live_events.append((event, EXTERNAL_ORIGIN))
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
        """Return how the frame is paced: not at all while fast-forwarding (rule 6).

        Otherwise as the installed doors pace it (a demo plays at the game's speed).

        Returns:
            Seconds (0.0: unpaced), or None for the target FPS.

        """
        if self.is_fast_forwarding:
            return 0.0
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
        """Return the installed doors' control events to apply again on this frame (rule 5).

        The session's (a replay of the session re-applies a breakpoint on a frame the scope
        played, so a bookmark there pauses), never the played recording's: a breakpoint an
        instant-replay journal kept was the live session's, applied then, and is not applied
        again inside its playback.

        Returns:
            The control events.

        """
        return self.base.control_events_for_frame(frame_number=frame_number)

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
        recording played. A fast-forwarded frame is silenced first (every sound it started
        stopped, music paused); after the last one, the silence ends (rule 6).
        """
        was_fast_forwarding = self.is_fast_forwarding
        if was_fast_forwarding:
            self._silencer.silence_frame()
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
        self.is_fast_forwarding = self.frames_played < self.fast_forward_frames
        if was_fast_forwarding and not self.is_fast_forwarding:
            # The shown frames play their sounds, and the music plays on
            self._silencer.finish()
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
        self: Self, *, live_scene: Scene, previous_scene: Scene | None, fps_event_seconds: float
    ) -> PlaybackSession:
        """Save what the scope's end restores, as the scope begins (rule 2).

        Args:
            live_scene: The active scene, stashed for the scope.
            previous_scene: ``SceneManager.previous_scene``, which the playback's own scene
                switches change.
            fps_event_seconds: When the live game last posted an FPS event.

        Returns:
            The session, holding the random streams and frame clock as they are now.

        """
        return PlaybackSession(
            sources=self.sources,
            live_scene=live_scene,
            saved_previous_scene=previous_scene,
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
        saved_previous_scene: ``SceneManager.previous_scene`` as the scope began (restored at
            its end: the playback's own scene switches set it to playback scenes).
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
    saved_previous_scene: Scene | None
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
            last complete frame), ``'diverged'``, ``'error'`` (an error in the scope, logged),
            ``'quit'`` (the run ended during the scope) or ``'ended_by_game'``
            (``SceneManager.end_playback``).
        frames_played: How many frames the scope compared with the recording.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    kind: PlaybackKind
    reason: PlaybackEndReason
    frames_played: int


def find_scene_class(*, name: str, module: str | None = None) -> type[Scene] | None:
    """Return the loaded ``Scene`` subclass a start names (rule 1).

    Only loaded classes are searched: nothing is imported from recording data. The class
    defined in ``module`` with the qualified name ``name`` is taken when exactly one is
    loaded. Otherwise a class is taken by its qualified name alone only where the modules
    cannot be compared, as ``check_recorded_game`` decides for a recording's game: no module
    recorded, or a game run as a script (``__main__``) on either side; then the one such class
    is taken and several are refused. A class of that name from another module is another
    game's scene: refused.

    Args:
        name: A class's qualified name (``SceneStart.scene_class``).
        module: The module it is defined in (``SceneStart.scene_module``), or None.

    Returns:
        The class, or None when no loaded subclass matches or several match by name alone
        (logged).

    """
    named_alike: list[type[Scene]] = []
    seen: set[type[Scene]] = set()
    unvisited: collections.deque[type[Scene]] = collections.deque([Scene])
    while unvisited:
        scene_class = unvisited.popleft()
        for subclass in scene_class.__subclasses__():
            if subclass not in seen:
                seen.add(subclass)
                unvisited.append(subclass)
                if subclass.__qualname__ == name:
                    named_alike.append(subclass)
    exact_matches = [scene_class for scene_class in named_alike if scene_class.__module__ == module]
    if len(exact_matches) == 1:
        return exact_matches[0]
    matches_by_name = [
        scene_class
        for scene_class in named_alike
        if module is None or SCRIPT_MODULE_NAME in {module, scene_class.__module__}
    ]
    if len(matches_by_name) > 1:
        LOG.warning('Several scene classes are named %s; which to rebuild is unknown', name)
        return None
    return matches_by_name[0] if matches_by_name else None


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
        replayed, or a scope is already starting or playing. Inside a scope that plays an
        instant-replay journal, the answer the frame being played recorded, and nothing is
        requested (``answered_playback_request``).

    """
    return answered_playback_request(
        manager=manager,
        request=lambda: _start_playback(
            manager=manager, header=header, frames=frames, then=then, options=options
        ),
    )


def answered_playback_request(*, manager: SceneManager, request: Callable[[], bool]) -> bool:
    """Answer a playback request as recorded inside a scope, else make it and keep its answer.

    The scene's code gets the same answers when its instant-replay journal is played back
    (glitchygames/instant_replay.py, rule 8): live, the answer is kept in the journal's frame
    (``SceneManager.note_playback_answer``); inside a scope playing the journal, the frame's
    recorded answer is returned (``SceneManager.recorded_playback_answer``) and the request is
    not made (scopes do not nest). Inside a scope whose recording holds no answer (a demo), the
    request is made, and refused as a nested scope.

    Args:
        manager: The running scene manager.
        request: Makes the request; returns whether a scope will begin.

    Returns:
        The answer.

    """
    recorded_answer = manager.recorded_playback_answer()
    if recorded_answer is not None:
        return recorded_answer
    granted = request()
    manager.note_playback_answer(granted=granted)
    return granted


def _start_playback(
    *,
    manager: SceneManager,
    header: dict[str, Any],
    frames: Sequence[dict[str, Any]],
    then: Scene,
    options: PlaybackOptions,
) -> bool:
    """Make the playback request ``start_playback`` describes (its answer is not kept here).

    Returns:
        As ``start_playback``, outside a scope.

    """
    kind = options.kind
    start_frame = options.start_frame
    start = _playable_start(frames=frames, options=options)
    if start is None or start.first_logic_frame is None:
        return False
    scene_class = find_scene_class(name=start.scene_class, module=start.scene_module)
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
                base=active_sources(),
                replay=replay,
                exit_on_input=options.exit_on_input,
                fast_forward_frames=options.fast_forward_frames,
            ),
            start=start,
            scene_class=scene_class,
            then=then,
            kind=kind,
            frame_count=len(frames) - start_frame,
            first_logic_frame=start.first_logic_frame,
        )
    )


def fast_forward_frame_count(
    *, frames: Sequence[dict[str, Any]], start_frame: int, shown_seconds: float
) -> int:
    """Return how many frames an instant replay fast-forwards before the seconds it shows.

    A frame is shown when the frame time from its start to the recording's end (its ``dt``
    and every later frame's, summed exactly, then rounded once to a float) is at most
    ``shown_seconds``; every earlier frame from ``start_frame`` is fast-forwarded (rule 7).
    So ten frames of ``dt`` d are shown for ``shown_seconds`` 10 * d, whatever float rounding
    a running sum would add.

    Args:
        frames: The recording's decoded frames.
        start_frame: The frame the playback starts at.
        shown_seconds: The frame time to show (``Scene.INSTANT_REPLAY_SECONDS``).

    Returns:
        The number of frames, from ``start_frame``, to fast-forward.

    """
    first_shown_frame = len(frames)
    seconds_to_end = Fraction(0)
    for frame_index in range(len(frames) - 1, start_frame - 1, -1):
        seconds_to_end += Fraction(frames[frame_index][DT_FIELD])
        if float(seconds_to_end) > shown_seconds:
            break
        first_shown_frame = frame_index
    return first_shown_frame - start_frame


def start_instant_replay(*, manager: SceneManager) -> bool:
    """Show the active scene's instant replay (``SceneManager.instant_replay``; rule 7).

    Args:
        manager: The running scene manager.

    Returns:
        True when the scope will begin at the start of the next frame; False (logged) when no
        journal is kept, the journal is past the scene's fast-forward budget, or a scope is
        already starting or playing. Inside a scope playing the journal, the answer the frame
        being played recorded, and nothing is requested (``answered_playback_request``).

    """
    return answered_playback_request(
        manager=manager, request=lambda: _start_instant_replay(manager=manager)
    )


def _start_instant_replay(*, manager: SceneManager) -> bool:
    """Make the playback request ``start_instant_replay`` describes (its answer is not kept here).

    Returns:
        As ``start_instant_replay``, outside a scope.

    """
    journal = manager.instant_replay_journal
    if journal is None:
        LOG.info('No instant replay: the active scene keeps no instant-replay journal')
        return False
    scene = journal.scene
    shown_seconds = scene.INSTANT_REPLAY_SECONDS
    budget_seconds = scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS
    if shown_seconds is None:
        LOG.info('No instant replay: %s sets no INSTANT_REPLAY_SECONDS', type(scene).__name__)
        return False
    if not journal.within_budget(maximum_seconds=budget_seconds):
        LOG.info(
            'No instant replay: %s s of %s would be re-simulated, past its %s s budget',
            journal.recorded_seconds,
            type(scene).__name__,
            budget_seconds,
        )
        return False
    # The scene itself, or the pause screen presenting it: the scope returns to what is shown
    then = manager.active_scene
    if then is None:
        LOG.info('No instant replay: no scene is active')
        return False
    recording = journal.as_recording()
    return _start_playback(
        manager=manager,
        header=recording.header,
        frames=recording.frames,
        then=then,
        options=PlaybackOptions(
            exit_on_input=False,
            kind=INSTANT_PLAYBACK,
            start_frame=recording.start_frame,
            fast_forward_frames=fast_forward_frame_count(
                frames=recording.frames,
                start_frame=recording.start_frame,
                shown_seconds=shown_seconds,
            ),
        ),
    )


def start_playback_from_recording(
    *,
    manager: SceneManager,
    path: Path,
    then: Scene,
    options: PlaybackOptions = DEFAULT_PLAYBACK_OPTIONS,
) -> bool:
    """Play a recording file in a playback scope (``start_playback``).

    A file cut off part way plays up to its last complete frame and ends as ``'truncated'``.

    Args:
        manager: The running scene manager.
        path: The recording.
        then: The scene to make active when the scope ends.
        options: How the scope plays.

    Returns:
        As ``start_playback``; also False (logged) for a missing or unreadable file.

    """
    return answered_playback_request(
        manager=manager,
        request=lambda: _start_playback_from_recording(
            manager=manager, path=path, then=then, options=options
        ),
    )


def _start_playback_from_recording(
    *, manager: SceneManager, path: Path, then: Scene, options: PlaybackOptions
) -> bool:
    """Read a recording file and make the playback request (its answer is not kept here).

    Returns:
        As ``start_playback_from_recording``, outside a scope.

    """
    try:
        read_result = read_trace_result(path=path)
    except (OSError, TraceFormatError) as error:
        LOG.warning('No %s: %s cannot be read: %s', options.kind, path, error)
        return False
    header = {name: value for name, value in read_result.trace.items() if name != FRAMES_FIELD}
    if is_cut_off(read_result=read_result):
        # Played up to its last complete frame, then ends as 'truncated'
        header[SOURCE_TRUNCATED_HEADER_FIELD] = True
    return _start_playback(
        manager=manager,
        header=header,
        frames=read_result.trace[FRAMES_FIELD],
        then=then,
        options=options,
    )
