"""Scene and SceneManager classes for the Glitchy Games Engine."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast, override

import pygame

from glitchygames import events
from glitchygames.backgrounds import (
    BackgroundPattern,
    active_default_background_pattern,
    background_pattern_surface,
)
from glitchygames.camera import Camera2D
from glitchygames.clock import frame_clock_seconds, measured_seconds
from glitchygames.collision import CollisionManager
from glitchygames.color import BLACK, RGB_COMPONENT_COUNT, RGBA_COMPONENT_COUNT
from glitchygames.debug import DebugFrameInfo, DebugOverlay
from glitchygames.debug.overlay import OVERLAY_KEYS
from glitchygames.effects.shake import ScreenShake, Shake, ShakeTarget
from glitchygames.effects.tween import TweenManager
from glitchygames.events.mouse import MousePointer
from glitchygames.input.action_map import DEFAULT_DEADZONE, normalized_axis_value
from glitchygames.input.input_devices import InputDevices
from glitchygames.input.rumble import ConnectedRumbleDevices, RumbleController
from glitchygames.input.state import (
    IDLE_INPUT,
    apply_snapshot_changes,
    current_input,
    set_current_input,
    snapshot_changes,
)
from glitchygames.instant_replay import InstantReplayJournal
from glitchygames.interfaces import SceneInterface, SpriteInterface
from glitchygames.opacity import OPAQUE, make_opaque
from glitchygames.pixel_snap import PixelSnapMode, set_active_default_snap_mode
from glitchygames.randomness import restore_stream_states
from glitchygames.recording import (
    is_input_post,
    is_live_game_post,
    live_game_code_running,
    live_game_posts,
    pending_code_post_count,
    pending_internal_posts,
    post_event,
    post_input_event,
    set_live_game_code_running,
)
from glitchygames.scene_start import (
    ResumeBridge,
    SceneStartCapture,
    begin_scene_start_capture,
    rebuild_scene,
)
from glitchygames.sources import (
    active_sources,
    advance_frame_clock,
    discard_scope_posts,
    has_scoped_sources,
    mark_frames_started,
    pop_scoped_sources,
    push_scoped_sources,
    redeliver_events,
    set_frame_clock_seconds,
    take_redelivered_events,
)
from glitchygames.supervision import PLAYBACK_KIND, ControlEvent
from glitchygames.timing import DEFAULT_TARGET_FPS
from glitchygames.world import aim_camera, is_world_positioned, position_world_sprites

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from glitchygames.audio.live import LiveAudio
    from glitchygames.engine import GameEngine
    from glitchygames.input.input_devices import InputDevice
    from glitchygames.input.rumble import RumbleDevice
    from glitchygames.input.state import InputSnapshot
    from glitchygames.replay.driver import ReplayResult
    from glitchygames.replay.playback import (
        PlaybackEndReason,
        PlaybackOutcome,
        PlaybackRequest,
        PlaybackSession,
    )
    from glitchygames.scene_start import SceneStart
    from glitchygames.sources import RedeliveredEvent
    from glitchygames.supervision import Supervisor
    from glitchygames.transitions import Transition

LOG = logging.getLogger('game.scenes')
LOG.addHandler(logging.NullHandler())

JITTER_SAMPLE_BUFFER_MAX_SIZE = 512
SHAKE_BORDER_COLOR = (0, 0, 0)  # Fills the strips a SCREEN shake uncovers

# Input dropped while a transition plays (SceneManager._process_transition_events): presses
# and motion, so nothing pressed during a ride acts when it ends. Releases (KEYUP,
# MOUSEBUTTONUP, JOYBUTTONUP, CONTROLLERBUTTONUP, FINGERUP), quit, window, focus and device
# events are still delivered, so held-input state (ActionMap) is never left stuck. Motion back
# to neutral is a release too and is delivered: see is_discarded_during_transition.
# CONTROLLERTOUCHPADUP is a release and is delivered. DROPFILE and DROPTEXT are deliberately
# delivered too, to the arriving scene: a file or text dropped during a ride should land.
TRANSITION_DISCARDED_EVENT_TYPES: frozenset[int] = frozenset({
    pygame.KEYDOWN,
    pygame.TEXTINPUT,
    pygame.MOUSEBUTTONDOWN,
    pygame.MOUSEMOTION,
    pygame.MOUSEWHEEL,
    pygame.JOYBUTTONDOWN,
    pygame.JOYAXISMOTION,
    pygame.JOYHATMOTION,
    pygame.JOYBALLMOTION,
    pygame.CONTROLLERBUTTONDOWN,
    pygame.CONTROLLERAXISMOTION,
    pygame.FINGERDOWN,
    pygame.FINGERMOTION,
    pygame.TEXTEDITING,
    pygame.CONTROLLERTOUCHPADDOWN,
    pygame.CONTROLLERTOUCHPADMOTION,
    pygame.MULTIGESTURE,
})


# Axis motions whose value is neutral (a stick back at rest) are releases
_AXIS_MOTION_EVENT_TYPES: frozenset[int] = frozenset({
    pygame.JOYAXISMOTION,
    pygame.CONTROLLERAXISMOTION,
})
_HAT_CENTRED: tuple[int, int] = (0, 0)


def is_discarded_during_transition(event: pygame.event.Event) -> bool:
    """Report whether a transition frame drops this event.

    Presses and motion (TRANSITION_DISCARDED_EVENT_TYPES) are dropped, except motion back to
    neutral, which releases a held stick or hat: an axis inside ActionMap's DEFAULT_DEADZONE
    (the value ActionMap treats as zero) or a hat at (0, 0).

    Args:
        event: A raw pygame event.

    Returns:
        True if the event is dropped, False if it is delivered.

    """
    if event.type not in TRANSITION_DISCARDED_EVENT_TYPES:
        return False
    if event.type in _AXIS_MOTION_EVENT_TYPES:
        position = normalized_axis_value(event_type=event.type, value=event.value)
        return abs(position) >= DEFAULT_DEADZONE
    if event.type == pygame.JOYHATMOTION:
        return tuple(event.value) != _HAT_CENTRED
    return True


def required_scene(*, next_scene: object) -> Scene | None:
    """Return the scene to switch or transition to, refusing anything that is not a Scene.

    The active scene must be a Scene (or a subclass): the scene manager reads the attributes
    Scene declares (its camera, scene start, snap mode, frame cap, key presses) directly. None
    stays None (a switch to None ends the run).

    Args:
        next_scene: The scene asked for.

    Returns:
        The scene, typed as a Scene, or None.

    Raises:
        TypeError: If next_scene is neither None nor a Scene.

    """
    if next_scene is None or isinstance(next_scene, Scene):
        return next_scene
    message = f'The next scene must be a Scene or None, not {type(next_scene).__name__}'
    raise TypeError(message)


class SceneManager(SceneInterface, events.EventManager):
    """Glitchy Games Scene Manager.

    The scene manager is responsible for managing the active scene,
    and for processing events.
    """

    _instance: ClassVar[SceneManager | None] = None
    log: ClassVar[logging.Logger] = LOG
    OPTIONS: ClassVar[dict[str, Any]] = {}
    # True once __init__ ran: SceneManager() returns the singleton, whose __init__ runs again
    _initialized: bool = False

    def __new__(cls) -> Self:
        """Create a new instance or return the existing singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # type: ignore[return-value] # ty: ignore[invalid-return-type]

    def __init__(self: Self) -> None:
        """Initialize the scene manager."""
        # Prevent re-initialization of singleton
        if self._initialized:
            return

        super().__init__()

        # None until the display is initialized (set later); get_surface() never raises
        self.screen = pygame.display.get_surface()
        self.update_type: str = 'update'
        self.fps_log_interval_ms: int = 1000
        self.target_fps: float = 0.0
        self.dt: float = 0.0
        # The last frame's measured start-to-start time (dt is what the frame-time door made of
        # it); only the performance statistics read it (_performance_frame_seconds)
        self._measured_frame_seconds: float = 0.0
        self.timer: Any = 0
        self._game_engine: GameEngine | None = None
        self.active_scene: Scene | None = None
        self.next_scene: Scene | None = self.active_scene
        self.previous_scene: Scene | None = self.active_scene
        self.quit_requested: bool = False
        # Frames finished this run; the doors' end_frame receives each frame's number
        self.frame_number: int = 0
        # Whether the last run_frame_step was a hold (the doors presented the latest frame again,
        # a watched replay's outer tick) rather than a frame
        self.last_step_was_held: bool = False
        self._initialize_supervision()

        # Scene transition support
        self._active_transition: Transition | None = None  # Transition object during effect
        # The requested switch, as its next scene and its transition
        self._pending_transition: tuple[Scene | None, Transition] | None = None

        self.clock: pygame.time.Clock = pygame.time.Clock()

        # SCREEN shake lives here (not on a scene) so it outlives scene switches
        self.screen_shake: ScreenShake = ScreenShake()
        # The display no longer shows what the surface holds (a shaken or overlaid frame was
        # presented, frames ran unpresented, or a playback scope ended): the next presented
        # frame updates the whole display (_show_frame)
        self._display_is_stale: bool = False
        # The time this frame spent presenting (_present_frame): left out of its processing time
        self._frame_present_seconds: float = 0.0
        self.debug_overlay: DebugOverlay = DebugOverlay()
        self.rumble: RumbleController = RumbleController()
        # The devices rumble is sent to (joysticks opened once, while their count holds), and
        # the live game's rumble controller while a playback scope plays on its own
        self._rumble_devices = ConnectedRumbleDevices()
        # A playback scope's own device lookups, asked through its doors and then dropped
        # (_rumble_devices_for_scope); new for each scope, so the live cache is never touched
        self._scope_rumble_devices = ConnectedRumbleDevices()
        self._live_rumble_behind_scope: RumbleController | None = None
        self._live_audio: LiveAudio | None = None

        # Jitter tracking attributes
        self._jitter_samples: list[int] = []
        self._jitter_last_log_ns: int = 0
        self._jitter_interval_start_ns: int = 0
        self._jitter_late_frames: int = 0
        self._timer_prev_deadline_ns: int | None = None
        # When the last FPS event was posted (frame-clock seconds); start() sets it
        self._previous_fps_event_seconds: float = 0.0
        # In-game playback (glitchygames/replay/playback.py): the scope requested for the next
        # frame, the scope in progress, and how the last one went
        self._requested_playback: PlaybackRequest | None = None
        # The scene that asked: the scope is dropped if it is gone when the next frame starts
        self._playback_requesting_scene: Scene | None = None
        # The scene whose setup() runs now (a request made there is that scene's)
        self._scene_in_setup: Scene | None = None
        self._playback_session: PlaybackSession | None = None
        self._last_playback_result: ReplayResult | None = None
        self._last_playback_outcome: PlaybackOutcome | None = None
        # True while _run_frame runs a frame, and while its supervisors run (end_playback is
        # honoured between frames and from the supervisor slot only)
        self._frame_in_progress = False
        self._in_supervisor_slot = False
        # The instant-replay journal of the scene that offers instant replay
        # (glitchygames/instant_replay.py): made as it is first set up, recording from its
        # first logic frame
        self._instant_replay_journal: InstantReplayJournal | None = None

        # Mark as initialized to prevent re-initialization
        self._initialized = True

    def _initialize_supervision(self: Self) -> None:
        """Make the supervision state (``__init__``): supervisors, handlers, control events."""
        # Called once per frame at the supervisor slot, in registration order (supervision.py)
        self._supervisors: list[Supervisor] = []
        # Those added by a playback scope's code: removed when the scope ends
        self._scope_supervisors: list[Supervisor] = []
        self._control_event_handlers: dict[str, list[Callable[[ControlEvent], None]]] = {}
        # Those added by a playback scope's code: removed when the scope ends
        self._scope_control_event_handlers: list[tuple[str, Callable[[ControlEvent], None]]] = []
        # This frame's control events; end_frame receives them, then the list starts over
        self._frame_control_events: list[ControlEvent] = []
        # Whether a supervisor or control event handler the live game added runs inside a
        # playback scope (what it adds or posts is the live game's, not the scope's) is kept by
        # the internal-post tracker, so post_event can tell its posts apart:
        # recording.live_game_code_running

    @classmethod
    def _reset(cls) -> None:
        """Reset the singleton for testing.

        Clears the singleton instance so the next call to SceneManager()
        creates a freshly initialized instance. This should only be used
        in tests.
        """
        instance = cls._instance
        if instance is not None:
            instance._initialized = False
        cls._instance = None

    def update_screen(self) -> None:
        """Update the screen reference when display becomes available."""
        if self.screen is None:
            self.screen = pygame.display.get_surface()

    @property
    def game_engine(self: Self) -> GameEngine | None:
        """The game engine.

        Returns:
            GameEngine | None: The game engine.

        """
        return self._game_engine

    @game_engine.setter
    def game_engine(self: Self, new_engine: GameEngine | None) -> None:
        self._game_engine = new_engine
        if self._game_engine:
            SceneManager.OPTIONS = self._game_engine.OPTIONS  # pyright: ignore[reportConstantRedefinition]
            self.update_type = self.OPTIONS['update_type']
            self.fps_log_interval_ms = self.OPTIONS['fps_log_interval_ms']
            self.target_fps = self.OPTIONS.get('target_fps', DEFAULT_TARGET_FPS)
            self.screen_shake.intensity = self.OPTIONS.get('screen_shake_intensity', 1.0)
            self.rumble.intensity = self.OPTIONS.get('rumble_intensity', 1.0)
            self.debug_overlay.is_visible = bool(self.OPTIONS.get('debug_overlay', False))
        self.log.info('Screen update type: %s', self.update_type)
        self.log.info('FPS Log Interval: %sms', self.fps_log_interval_ms)
        self.log.info('Target FPS: %s', self.target_fps)

        # Configure performance manager with the same log interval and target FPS
        from glitchygames.performance import performance_manager

        performance_manager.set_fps_log_interval(self.fps_log_interval_ms)
        performance_manager.set_target_fps(self.target_fps)

    @property
    def input_devices(self: Self) -> InputDevices:
        """Every joystick and game controller the game sees (glitchygames/input/input_devices.py).

        The engine's; without an engine (a bare scene manager), an empty registry.
        """
        game_engine = self._game_engine
        return InputDevices() if game_engine is None else game_engine.input_devices

    def on_input_device_added(self: Self, *, device: InputDevice) -> None:
        """Tell the active scene a device was connected (GameEngine, after a device event).

        Args:
            device: The device the game sees from now on.

        """
        if self.active_scene is not None:
            self.active_scene.on_input_device_added(device=device)

    def on_input_device_removed(self: Self, *, device: InputDevice) -> None:
        """Tell the active scene a device was disconnected (GameEngine, after a device event).

        Args:
            device: The device the game no longer sees.

        """
        if self.active_scene is not None:
            self.active_scene.on_input_device_removed(device=device)

    # This enables collided_sprites in sprites.py, since SceneManager is
    # not a scene, but is the entry point for event proxies.
    @property
    def all_sprites(self: Self) -> pygame.sprite.LayeredDirty[Any] | None:
        """The active scene's sprite group.

        Returns:
            pygame.sprite.LayeredDirty[Any] | None: The active scene's sprite group.

        """
        if self.active_scene:
            return self.active_scene.all_sprites

        return None

    @property
    def active_scene_start(self: Self) -> SceneStart | None:
        """How the active scene began (glitchygames/scene_start.py), if captured.

        None without an active scene, or when its start was not captured.
        """
        if self.active_scene is None:
            return None
        return self.active_scene.scene_start

    @property
    def instant_replay_journal(self: Self) -> InstantReplayJournal | None:
        """The journal of the scene that offers instant replay (glitchygames/instant_replay.py).

        None when no scene keeps one, until the scene's first logic frame began, and while a
        playback scope plays (the scope's scene is not the live session's; the journal waits,
        suspended, and is back once the scope ended). Kept while the scene is behind the pause
        screen.
        """
        journal = self._instant_replay_journal
        if journal is None or not journal.is_recording or has_scoped_sources():
            return None
        return journal

    def journal_pumped_events(
        self: Self,
        *,
        raw_events: list[pygame.event.Event],
        posts_before_pump: list[tuple[int, dict[str, Any]]],
        origins: list[str] | None,
        redelivered_events: list[RedeliveredEvent],
    ) -> None:
        """Hand one pump's batch to the instant-replay journal (``GameEngine._pump_events``).

        Nothing while no journal is kept or a playback scope serves the frame (its scene is
        not the live session's).

        Args:
            raw_events: The doors' batch, as they returned it.
            posts_before_pump: A copy of the internal-post tracker's posts before the pump.
            origins: Each event's origin when a replay's merge knows them, else None.
            redelivered_events: The events delivered before the batch, with their origins.

        """
        journal = self._instant_replay_journal
        if journal is None or has_scoped_sources():
            return
        journal.add_event_batch(
            raw_events=raw_events,
            posts_before_pump=posts_before_pump,
            origins=origins,
            redelivered_events=redelivered_events,
        )

    def recorded_playback_answer(self: Self) -> bool | None:
        """Return what a playback request got in the frame being played, inside a scope.

        A scene played back from its instant-replay journal asks for playbacks where the live
        scene did (an instant replay after every goal): each request is answered with the next
        answer that frame recorded, and nothing is requested (scopes do not nest;
        glitchygames/instant_replay.py, rule 8). ``start_playback`` asks this first.

        Returns:
            The recorded answer; None outside a scope, or when the frame recorded none left.

        """
        session = self._playback_session
        if session is None:
            return None
        answers = session.sources.replay.recorded_playback_answers
        return answers.popleft() if answers else None

    def note_playback_answer(self: Self, *, granted: bool) -> None:
        """Keep what a playback request got in the instant-replay journal (live play only).

        Args:
            granted: What ``start_playback`` returned.

        """
        journal = self._instant_replay_journal
        if journal is not None and not has_scoped_sources():
            journal.add_playback_answer(granted=granted)

    def _begin_journal_frame(self: Self) -> None:
        """Begin or resume the instant-replay journal at the top of the frame (rules 3 and 7).

        It begins on its scene's first logic frame, and resumes, writing the frame's resume
        bridge, on the first frame after a playback scope that presents its scene again (the
        scene itself, or the pause screen showing it). Never inside a scope or a transition.
        """
        journal = self._instant_replay_journal
        if journal is None or has_scoped_sources() or self._active_transition is not None:
            return
        if journal.is_suspended:
            if self._presented_scene() is journal.scene:
                input_before = current_input()
                journal.resume(
                    bridge=ResumeBridge(
                        frame_clock_seconds=frame_clock_seconds(),
                        fps_event_seconds=self._previous_fps_event_seconds,
                        earlier_internal_event_count=pending_code_post_count(),
                        input_before=snapshot_changes(previous=IDLE_INPUT, current=input_before),
                    ),
                    input_before=input_before,
                )
            return
        # The journal's scene is a Scene (InstantReplayJournal reads its scene_start as it is made)
        start = journal.scene.scene_start
        if (
            not journal.is_recording
            and journal.scene is self.active_scene
            and start is not None
            and start.first_logic_frame is not None
        ):
            journal.begin(start=start, input_before_start=current_input())

    def _apply_resume_bridge(self: Self) -> None:
        """Inside a scope, start a frame its recording resumed after a scope as it began.

        The scope's replay holds the frame's resume bridge (glitchygames/replay/driver.py,
        rule 18): the frame clock, the FPS event timer and the polled input are set to what the
        recorded scene resumed with, at the top of the frame, before any of its work; the frame
        effects the recorded scope's end cleared (``_clear_frame_effects``) are cleared too.
        """
        session = self._playback_session
        if session is None:
            return
        bridge = session.sources.replay.frame_bridge
        if bridge is None:
            return
        # What the recorded scope's end did (_exit_playback): the SCREEN shake and sustained
        # rumble stopped, so a JITTER screen shake no longer draws from the shared shake stream.
        # (Its stream restore needs no repeat: streams are restored in place, so they hold the
        # states they had before the scope, which they hold here too.)
        self._clear_frame_effects()
        self._restore_logic_frame_state(
            frame_clock_seconds=bridge.frame_clock_seconds,
            fps_event_seconds=bridge.fps_event_seconds,
            input_before=apply_snapshot_changes(previous=IDLE_INPUT, changes=bridge.input_before),
        )

    def _restore_logic_frame_state(
        self: Self,
        *,
        frame_clock_seconds: float,
        fps_event_seconds: float,
        input_before: InputSnapshot,
    ) -> None:
        """Set what a recorded logic frame began with, at the top of the frame (inside a scope).

        A playback's first frame (``FirstLogicFrame``, ``_enter_playback``) and a frame its
        recording resumed in after a scope (``ResumeBridge``, ``_apply_resume_bridge``) both
        begin with the recorded frame clock, FPS event timer and polled input.

        Args:
            frame_clock_seconds: The frame clock the recorded frame began at.
            fps_event_seconds: When the last FPS event was posted, on that frame clock.
            input_before: The polled input the recorded frame's logic read.

        """
        set_frame_clock_seconds(seconds=frame_clock_seconds)
        self._previous_fps_event_seconds = fps_event_seconds
        set_current_input(snapshot=input_before)

    def _prepare_instant_replay_journal(self: Self, *, scene: Scene) -> None:
        """Make the journal of a scene that offers instant replay, as it is first set up.

        Called before its ``setup()`` (glitchygames/instant_replay.py, rule 2). A later setup
        (resuming it from the pause screen) keeps its journal; a scene whose start is not
        captured and a scene a playback scope builds keep none.

        Args:
            scene: The scene being set up.

        """
        if scene.INSTANT_REPLAY_SECONDS is None:
            return
        start = scene.scene_start
        if start is None or start.first_logic_frame is not None or has_scoped_sources():
            return
        journal = self._instant_replay_journal
        if journal is not None and journal.scene is scene:
            return
        self._end_instant_replay_journal()
        game_engine = self.game_engine
        self._instant_replay_journal = InstantReplayJournal(
            scene=scene, game=game_engine.game if game_engine is not None else None
        )

    def _journal_frame(self: Self, *, frame_dt: float) -> None:
        """Add the frame just ended to the journal, or end the journal if its scene has gone.

        The journal goes on while its scene, or the pause screen presenting it (the active
        scene's ``debug_subject``), ends the frame (glitchygames/instant_replay.py, rules 5, 6
        and 9).

        Args:
            frame_dt: The frame's raw dt, read before the frame ran.

        """
        journal = self._instant_replay_journal
        if journal is None:
            return
        if self._presented_scene() is not journal.scene:
            self._end_instant_replay_journal()
            return
        journal.add_frame(
            dt=frame_dt,
            scene=self.active_scene,
            control_events=self._frame_control_events,
            input_snapshot=current_input(),
        )
        # Past the fast-forward budget no instant replay can be shown again (the frame time a
        # playback re-runs only grows), so nothing more is kept (rule 11)
        budget_seconds = journal.scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS
        if not journal.within_budget(maximum_seconds=budget_seconds):
            LOG.debug(
                'The instant-replay journal of %s passed its %s s budget and is dropped',
                type(journal.scene).__name__,
                budget_seconds,
            )
            self._end_instant_replay_journal()

    def _presented_scene(self: Self) -> Scene | None:
        """Return the scene the player sees: the active scene, or the scene it presents.

        A pause screen presents the paused game (``Scene.debug_subject``).

        Returns:
            The scene (None without an active scene).

        """
        if self.active_scene is None:
            return None
        return self.active_scene.debug_subject

    def _end_instant_replay_journal(self: Self) -> None:
        """Close and drop the instant-replay journal, if one is kept (instant_replay.py, rule 9)."""
        journal, self._instant_replay_journal = self._instant_replay_journal, None
        if journal is not None:
            journal.close()

    @property
    def playback_session(self: Self) -> PlaybackSession | None:
        """The playback scope in progress (glitchygames/replay/playback.py), or None."""
        return self._playback_session

    @property
    def last_playback_result(self: Self) -> ReplayResult | None:
        """How the last playback scope's replay went (kept when it ended), or None."""
        return self._last_playback_result

    @property
    def last_playback_outcome(self: Self) -> PlaybackOutcome | None:
        """How and why the last playback scope ended, or None."""
        return self._last_playback_outcome

    def request_playback(self: Self, *, request: PlaybackRequest) -> bool:
        """Enter a playback scope at the start of the next frame (glitchygames/replay/playback.py).

        A scope begins between frames, so the rebuilt scene's first frame is a whole frame, as
        the recorded one was, and the frame that asked runs to its end on the live doors. If
        the active scene changed by then (a ``next_scene`` switch at the end of the frame that
        asked), the request is dropped (logged): the scene to return to has gone.

        Args:
            request: The scope to enter (``start_playback`` builds it).

        Returns:
            False (logged) when a scope is already requested or in progress: scopes do not
            nest. True otherwise.

        """
        if self._requested_playback is not None or self.in_playback_scope:
            LOG.warning('A playback is already starting or playing; %s not started', request.kind)
            return False
        self._requested_playback = request
        # A scene asking from its setup() (a title screen starting the next demo as a demo
        # returns to it) is the one active from then on
        self._playback_requesting_scene = (
            self._scene_in_setup if self._scene_in_setup is not None else self.active_scene
        )
        return True

    def play_recording(self: Self, *, path: Path, then: Scene) -> None:
        """Play a recording as an attract-mode demo, then return to ``then``.

        The demo plays in a playback scope (glitchygames/replay/playback.py) from the start of
        the next frame, at the game's speed, and ends at the recording's end, at the first key
        or button press (``exit_on_input``), at a divergence (logged at WARNING, ``demo
        diverged: <description>``) or at the recording's own quit. A recording cut off part
        way plays to its last complete frame and ends as ``truncated``. A recording that
        cannot be played (missing, unreadable, of another game, with no scene start to
        begin at) is logged at WARNING, naming the demo and the reason, and nothing starts;
        so is a request while another playback is starting or playing. How it ended:
        ``last_playback_outcome``.

        Args:
            path: The recording.
            then: The scene to make active when the demo ends (usually the scene asking).

        """
        # Function-level import, for layering: glitchygames.replay.playback imports
        # glitchygames.scenes (it needs Scene), and scenes must not import replay at runtime, so
        # a module-level import here would be a cycle.
        from glitchygames.replay.playback import (
            DEMO_PLAYBACK,
            PlaybackOptions,
            start_playback_from_recording,
        )

        start_playback_from_recording(
            manager=self,
            path=path,
            then=then,
            options=PlaybackOptions(exit_on_input=True, kind=DEMO_PLAYBACK),
        )

    def instant_replay(self: Self) -> bool:
        """Show the active scene's last ``INSTANT_REPLAY_SECONDS``, then go on where it was.

        The scene is rebuilt from its start in a playback scope from the start of the next
        frame and plays its instant-replay journal (glitchygames/instant_replay.py): the frames
        before the last ``INSTANT_REPLAY_SECONDS`` of frame time run unseen, unpaced and silent,
        the rest are shown at the game's pace, then the live scene, never touched, goes on
        exactly where it was (glitchygames/replay/playback.py, rules 6 and 7). The player's
        presses do not end it; the game may, with ``end_playback``. How it ended:
        ``last_playback_outcome``.

        Returns:
            True when the instant replay will begin. False (logged; nothing happens) when the
            active scene keeps no journal (its class sets no ``INSTANT_REPLAY_SECONDS``, or
            its first logic frame has not run), the journal is past the scene's
            ``MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS``, or a playback is already starting or
            playing. Inside a playback of the journal, what the recorded scene was answered
            (nothing is requested: scopes do not nest).

        """
        # Function-level import, for layering (as in play_recording)
        from glitchygames.replay.playback import start_instant_replay

        return start_instant_replay(manager=self)

    def end_playback(self: Self) -> None:
        """End the playback scope in progress (a demo, an instant replay); the game goes on.

        Honoured from a supervisor (``add_supervisor``; the scope then ends once that frame
        ended, so the frame is played and compared whole) and between frames (at once). Its
        outcome's reason is ``'ended_by_game'``. Asked anywhere else in a frame, it is ignored
        (logged at DEBUG): inside a scope the only scene code running is the played scene's,
        whose call did nothing in its original run (no scope was playing then), as
        ``recorded_playback_answer`` keeps a playback request's answer. A control event
        handler's call (``add_control_event_handler``) is honoured only when a supervisor's own
        ``record_control_event`` ran it, inside the slot; the handlers of a frame's re-applied
        control events (a replayed breakpoint) run before the supervisors, outside the slot, so
        their call is ignored. Nothing when no scope is in progress (a requested one still
        begins).

        The player's presses reach no scene during an instant replay; a supervisor reads the
        player's polled input from ``playback_player_input`` to decide when to end it.
        """
        session = self._playback_session
        if session is None:
            return
        if not self._frame_in_progress:
            self._exit_playback(reason='ended_by_game')
            return
        if not self._in_supervisor_slot:
            LOG.debug('end_playback() asked by the played scene is ignored: it did nothing live')
            return
        sources = session.sources
        # First reason found wins, as PlaybackSources._note_end keeps it (the class has no
        # room for a public method that would do this)
        if sources.end_reason is None:
            sources.end_reason = 'ended_by_game'

    @property
    def playback_player_input(self: Self) -> InputSnapshot | None:
        """The player's polled input while a playback scope plays, or None outside one.

        The installed doors' latest snapshot (``current_input()`` is the recording's inside
        a scope): a supervisor reads it to end an instant replay at the player's press
        (``end_playback``).
        """
        session = self._playback_session
        if session is None:
            return None
        return session.sources.last_base_snapshot

    def request_transition(
        self: Self,
        next_scene: Scene | None,
        transition: Transition,
    ) -> None:
        """Request a scene switch with a visual transition effect.

        The transition starts on the next frame. During the transition,
        normal scene updates and rendering are paused.

        Args:
            next_scene: The scene to transition to.
            transition: A Transition object (FadeTransition, SlideTransition, etc.).

        """
        self._pending_transition = (required_scene(next_scene=next_scene), transition)

    def _start_transition(self: Self, next_scene: Scene | None, transition: Transition) -> None:
        """Capture screenshots and begin a transition effect.

        Args:
            next_scene: The scene to transition to.
            transition: The Transition object.

        """
        old_surface = self._capture_outgoing_scene()

        # Set up the new scene (off-screen) so we can capture it
        self.previous_scene = self.active_scene
        self._clear_outgoing_scene_pending_switch()
        self._cleanup_current_scene()
        scene = next_scene
        self._setup_new_scene(scene)
        # Its first logic frame comes after the ride, which its playback repeats the arrival of
        # (glitchygames/scene_start.py, rule 7)
        start_capture = scene.scene_start_capture if scene is not None else None
        if (
            start_capture is not None
            and start_capture.start is not None
            and start_capture.start.first_logic_frame is None
        ):
            start_capture.arrived_by_transition = True
        self.active_scene = scene
        self._configure_active_scene()

        new_surface = self._capture_arriving_scene()

        # Start the transition effect with both screenshots
        transition.start(old_surface, new_surface)
        self._active_transition = transition

    def _capture_outgoing_scene(self: Self) -> pygame.Surface:
        """Screenshot the scene being left, without its player and without a WORLD shake.

        The player is hidden so the transition can draw its own player overlay without
        doubling, and shown again afterwards. A world-space player is hidden with ``hidden``
        (the engine owns its ``visible``) and re-culled afterwards; a screen-space player's
        ``visible`` is written directly.

        Returns:
            A copy of the screen showing the outgoing scene.

        """
        # Looked up by name: player is the game's own attribute, which a scene may not have
        old_player = getattr(self.active_scene, 'player', None) if self.active_scene else None
        old_player_was_hidden = self._hide_world_player_for_capture(old_player)

        # Clear a WORLD shake so the old-floor screenshot is unshaken.
        camera_was_shaking = False
        if self.active_scene is not None and self.active_scene.camera.shake_effect.is_active:
            camera_was_shaking = True
            self.active_scene.camera.shake_effect.clear()
            self.active_scene.apply_camera_to_sprites()

        recapture_old_scene = bool(
            (old_player is not None or camera_was_shaking) and self.active_scene and self.screen
        )
        if recapture_old_scene:
            # Re-place world sprites (the WORLD shake they were placed with is now cleared);
            # a world-space player is already hidden, so positioning culls it
            self._position_active_world_sprites()
        if old_player is not None:
            if old_player_was_hidden is None:
                old_player.visible = False
            old_player.dirty = 0
        if recapture_old_scene:
            assert self.active_scene is not None
            assert self.screen is not None
            self.active_scene.update()
            self.active_scene.render(self.screen)
        old_surface = self.screen.copy() if self.screen else pygame.Surface((800, 600))
        if old_player is not None:
            if old_player_was_hidden is None:
                old_player.visible = True
            else:
                self._restore_world_player_after_capture(
                    player=old_player, was_hidden=old_player_was_hidden
                )
            old_player.dirty = 2
        return old_surface

    @staticmethod
    def _hide_world_player_for_capture(player: object) -> bool | None:
        """Hide a world-space player with ``hidden`` for a transition capture.

        Returns:
            The player's previous ``hidden`` value, or None when there is no player or it is
            screen space (its ``visible`` is written directly instead).

        """
        if player is None or not is_world_positioned(player):
            return None
        # Looked up by name: a game's world sprite need not declare hidden (World Space)
        was_hidden = bool(getattr(player, 'hidden', False))
        cast('Any', player).hidden = True
        return was_hidden

    def _restore_world_player_after_capture(
        self: Self, *, player: object, was_hidden: bool
    ) -> None:
        """Give a world-space player back its ``hidden`` value and let the engine re-cull it.

        Positioning again sets ``visible`` from the screen and ``hidden``, so a player off
        screen stays invisible instead of being shown until the next frame.

        Args:
            player: The world-space player.
            was_hidden: Its ``hidden`` value before the capture.

        """
        cast('Any', player).hidden = was_hidden
        self._position_active_world_sprites()

    def _capture_arriving_scene(self: Self) -> pygame.Surface:
        """Screenshot the scene being entered (already set up and active), without its player.

        Snaps the camera (no lerp) and renders, so the screenshot shows the correct view for
        the transition: to the scene's camera target on the camera's followed axes only (an
        unfollowed axis stays where setup() put it), or, when camera_target() is None, to the
        player's position on both axes, as before follow targets existed. The player sprite
        is hidden during the capture (the transition draws its own player overlay) and
        restored afterwards.

        Returns:
            A copy of the screen showing the arriving scene.

        """
        if self.active_scene and self.screen:
            camera = self.active_scene.camera
            # Looked up by name: player is the game's own attribute, which a scene may not have
            player = getattr(self.active_scene, 'player', None)
            # A world-space player is hidden with hidden (positioning then culls it); a
            # screen-space player's visible is written directly, as it always was
            player_was_hidden = self._hide_world_player_for_capture(player)
            player_was_visible = True
            if player is not None:
                if player_was_hidden is None:
                    player_was_visible = getattr(player, 'visible', True)
                    player.visible = False
                player.dirty = 0
                camera_target = self.active_scene.camera_target()
                if camera_target is None:
                    # A screen-space player may have no world position: the camera snaps to 0
                    camera.snap_to(
                        target_x=getattr(player, 'world_x', 0.0),
                        target_y=getattr(player, 'world_y', 0.0),
                    )
                else:
                    target_x, target_y = camera_target
                    camera.snap_followed_axes_to(target_x=target_x, target_y=target_y)
            self.active_scene.dt_tick(0.001)
            # Place the arriving scene's world sprites, so its screenshot shows them in place
            self._position_active_world_sprites()
            if player is not None:
                if player_was_hidden is None:
                    player.visible = False
                player.dirty = 0
            self.active_scene.update()
            self.active_scene.render(self.screen)
            # Restore the player for when gameplay resumes
            if player is not None:
                if player_was_hidden is None:
                    player.visible = player_was_visible
                else:
                    self._restore_world_player_after_capture(
                        player=player, was_hidden=player_was_hidden
                    )
                player.dirty = 2
        return self.screen.copy() if self.screen else pygame.Surface((800, 600))

    def _finalize_transition(self: Self) -> None:
        """Complete a transition and resume normal scene rendering."""
        self._active_transition = None
        # Force a full redraw of the active scene (the frame loop stops when there is none, so
        # a transition never finishes without one)
        if self.active_scene:  # pragma: no branch - see above
            for sprite in self.active_scene.all_sprites:
                sprite.dirty = max(sprite.dirty, 1)

    @property
    def in_playback_scope(self: Self) -> bool:
        """True while a playback scope's doors are pushed (glitchygames/replay/playback.py).

        The one answer to "is a scope playing" for ownership: it holds from the moment the
        scope's doors are pushed until they are popped, including while its scene is cleaned
        up at its end (``playback_session`` is the scope's data, cleared first).
        """
        return has_scoped_sources()

    def _added_by_scope_code(self: Self) -> bool:
        """Report whether something added now belongs to the playback scope (rule 4 there).

        Returns:
            True inside a scope, unless a supervisor or control event handler the live game
            added is running (what live code adds is the live game's).

        """
        return self.in_playback_scope and not live_game_code_running()

    def add_supervisor(self: Self, *, supervisor: Supervisor) -> None:
        """Call ``supervisor`` once per frame at the supervisor slot (supervision.py).

        One the scope's code adds while a playback scope plays (the rebuilt scene's setup() or
        cleanup(), its event handlers) belongs to the scope and is removed when it ends
        (glitchygames/replay/playback.py, rule 4); supervisors added before the scope began,
        or by a live supervisor or handler while it plays, are the live game's.
        """
        self._supervisors.append(supervisor)
        if self._added_by_scope_code():
            self._scope_supervisors.append(supervisor)

    def remove_supervisor(self: Self, *, supervisor: Supervisor) -> None:
        """Stop calling ``supervisor``; unknown supervisors are ignored."""
        if supervisor in self._supervisors:
            self._supervisors.remove(supervisor)
        if supervisor in self._scope_supervisors:
            self._scope_supervisors.remove(supervisor)

    def add_control_event_handler(
        self: Self, *, kind: str, handler: Callable[[ControlEvent], None]
    ) -> None:
        """Call ``handler`` for every control event of ``kind`` (live or replayed).

        One the scope's code adds while a playback scope plays belongs to the scope and is
        removed when it ends, as a supervisor is (``add_supervisor``).
        """
        self._control_event_handlers.setdefault(kind, []).append(handler)
        if self._added_by_scope_code():
            self._scope_control_event_handlers.append((kind, handler))

    def _remove_scope_supervision(self: Self) -> None:
        """Remove the supervisors and control event handlers a playback scope's code added."""
        # Every scope supervisor and handler is also in the live lists: add_supervisor and
        # add_control_event_handler add to both, remove_supervisor removes from both
        for supervisor in self._scope_supervisors:
            self._supervisors.remove(supervisor)
        self._scope_supervisors.clear()
        for kind, handler in self._scope_control_event_handlers:
            self._control_event_handlers[kind].remove(handler)
        self._scope_control_event_handlers.clear()

    def _run_live_or_scope_code(
        self: Self, *, is_scope_code: bool, call: Callable[[], None]
    ) -> None:
        """Run a supervisor or handler, noting whether the live game's code is running.

        Inside a playback scope, what the live game's own supervisor or handler adds is the
        live game's (``_added_by_scope_code``), and so is what it posts: ``post_event`` marks
        those posts (``recording.live_game_posts``) so the scope delivers them to the live game
        instead of dropping them or handing them to its replay (glitchygames/replay/playback.py,
        rules 4 and 5). A scope's handler run from a live supervisor is the scope's again.

        Args:
            is_scope_code: True for one a playback scope's code added.
            call: Runs it.

        """
        was_running = live_game_code_running()
        set_live_game_code_running(running=self.in_playback_scope and not is_scope_code)
        try:
            call()
        finally:
            set_live_game_code_running(running=was_running)

    def reset_supervision(self: Self) -> None:
        """Forget every supervisor, control event handler and pending control event.

        ``begin_run`` calls it, so a run never inherits an earlier run's supervision from this
        singleton.
        """
        self._supervisors.clear()
        self._scope_supervisors.clear()
        self._control_event_handlers.clear()
        self._scope_control_event_handlers.clear()
        self._frame_control_events = []

    def begin_run(self: Self) -> None:
        """Start a new run on this singleton: nothing an earlier run left carries over.

        ``GameEngine.__init__`` calls it (a second engine in one process, a recording and then
        its replay, shares this scene manager): frames are numbered from 0 (as
        ``reset_sources()`` restarted the frame clock), supervision is reset
        (``reset_supervision``), and the quit request, the pacing deadline, the SCREEN shake,
        the stale-display flag, a requested or finished playback scope's state and the
        instant-replay journal are cleared.
        """
        self.frame_number = 0
        self.reset_supervision()
        self.quit_requested = False
        self._timer_prev_deadline_ns = None
        self.screen_shake.clear()
        self._display_is_stale = False
        self._requested_playback = None
        self._playback_requesting_scene = None
        self._last_playback_result = None
        self._last_playback_outcome = None
        self._end_instant_replay_journal()

    def record_control_event(self: Self, *, kind: str, data: Mapping[str, Any]) -> None:
        """Record a supervisor action in this frame and hand it to its handlers.

        The event is recorded (with a read-only copy of ``data``) before any handler runs.
        Every handler for ``kind`` runs, in registration order, even when an earlier one
        raises; then the first handler exception is re-raised, and any later ones are logged,
        so a broken handler fails loudly without silently skipping the others.
        """
        control_event = ControlEvent(kind=kind, data=data)
        self._frame_control_events.append(control_event)
        first_error: Exception | None = None
        scope_handlers = [
            scope_handler
            for scope_kind, scope_handler in self._scope_control_event_handlers
            if scope_kind == kind
        ]
        for handler in list(self._control_event_handlers.get(kind, [])):
            try:
                self._run_live_or_scope_code(
                    is_scope_code=handler in scope_handlers,
                    call=lambda handler=handler: handler(control_event),
                )
            except Exception as error:
                if first_error is None:
                    first_error = error
                else:
                    LOG.exception('Another %r control event handler failed', kind)
        if first_error is not None:
            raise first_error

    def _run_supervisor_slot(self: Self) -> None:
        """Apply this frame's scheduled control events, then call every supervisor.

        The doors schedule the control events a recording holds for this frame (live play has
        none), so a replay re-applies them on the frame they happened in. Supervisors run in
        registration order; the list is copied so one may remove itself.
        """
        for control_event in active_sources().control_events_for_frame(
            frame_number=self.frame_number
        ):
            self.record_control_event(kind=control_event.kind, data=control_event.data)
        self._in_supervisor_slot = True
        try:
            for supervisor in list(self._supervisors):
                self._run_live_or_scope_code(
                    is_scope_code=supervisor in self._scope_supervisors,
                    call=lambda supervisor=supervisor: supervisor.on_frame(
                        frame_number=self.frame_number, scene=self.active_scene
                    ),
                )
        finally:
            self._in_supervisor_slot = False

    def _update_frame_services(self: Self) -> None:
        """Advance services that outlive scenes: screen shake, rumble and live audio."""
        self.debug_overlay.record_frame(frame_seconds=self._performance_frame_seconds())
        self.screen_shake.update(self.dt)

        shakers = [self.screen_shake]
        active_camera = self._active_camera()
        if active_camera is not None:
            shakers.append(active_camera.shake_effect)
        # None without an engine (a bare SceneManager) and in joystick mode
        game_engine = self.game_engine
        controller_manager = game_engine.controller_manager if game_engine is not None else None
        self.rumble.update(
            shakers=shakers,
            dt=self.dt,
            # A playback never rumbles the player's real devices (playback.py, rule 8)
            devices=(
                (lambda: self._rumble_devices_for_scope(controller_manager=controller_manager))
                if self.in_playback_scope
                else lambda: self._rumble_devices.find(controller_manager=controller_manager)
            ),
        )

        # The pending transition counts: a ride creates its motor before transition_to starts it
        if self._live_audio is not None:
            pending_transition = (
                self._pending_transition[1] if self._pending_transition is not None else None
            )
            # A playback scope's stashed live scene, the scene it returns to and the live
            # previous scene (the game behind a pause screen the scope began from) wait behind
            # it: their voices pause, then play on (never released for good). The playback's own
            # scene switches set previous_scene to playback scenes, so the live one is the saved
            session = self._playback_session
            paused_owners = (
                []
                if session is None
                else [
                    owner
                    for owner in (session.live_scene, session.then, session.saved_previous_scene)
                    if owner is not None
                ]
            )
            self._live_audio.update(
                active_scene=self.active_scene,
                previous_scene=self.previous_scene,
                active_transitions=(self._active_transition, pending_transition),
                paused_owners=paused_owners,
            )

    def _rumble_devices_for_scope(
        self: Self, *, controller_manager: object | None
    ) -> list[RumbleDevice]:
        """Ask the scope's doors for the devices as a live send would, then send to none.

        A playback never rumbles the player's real devices (playback.py, rule 8), but each send
        still asks the played recording's devices door, as the recorded run did: a joystick
        count it answered for rumble and nobody asked would be read by the played scene's next
        enumeration of its own.

        Args:
            controller_manager: GameEngine.controller_manager; None in joystick mode.

        Returns:
            An empty list.

        """
        self._scope_rumble_devices.find(controller_manager=controller_manager)
        return []

    @property
    def live_audio(self: Self) -> LiveAudio:
        """Live synth voices, created on first use from the engine's reserved channels."""
        if self._live_audio is None:
            from glitchygames.audio.live import LiveAudio

            game_engine = self.game_engine
            channels = game_engine.live_voice_channels if game_engine is not None else ()
            self._live_audio = LiveAudio(channel_indices=channels)
        return self._live_audio

    def _debug_frame_info(
        self: Self, *, shake_offset: tuple[float, float], inspected_scene_label: str | None
    ) -> DebugFrameInfo:
        """Gather the per-frame engine readings the debug overlay displays.

        Args:
            shake_offset (tuple[float, float]): The current SCREEN shake offset.
            inspected_scene_label (str | None): Name of the scene the overlay inspects when it
                is not the active scene (a paused game), else None.

        Returns:
            DebugFrameInfo: The readings for this frame.

        """
        live_voice_count = (
            self._live_audio.playing_voice_count if self._live_audio is not None else None
        )
        frame_input = current_input()
        mouse_position = frame_input.mouse_position if frame_input.mouse_focused else None
        return DebugFrameInfo(
            target_fps=float(self.target_fps),
            live_voice_count=live_voice_count,
            rumble_levels=self.rumble.sent_levels,
            screen_shake_offset=shake_offset,
            mouse_position=mouse_position,
            inspected_scene_label=inspected_scene_label,
        )

    def _active_scene_has_focused_sprite(self: Self) -> bool:
        """Report whether a sprite in the active scene has keyboard focus.

        Returns:
            bool: True when any sprite's is_active is True; False with no active scene.

        """
        if self.active_scene is None:
            return False
        # `is True` rather than truthiness: Mock sprites report a truthy Mock for any attribute
        return any(
            getattr(sprite, 'is_active', False) is True for sprite in self.active_scene.all_sprites
        )

    def on_key_down_event(self: Self, event: events.KeyEvent) -> None:
        """Handle the debug overlay keys, then forward key-down events as the proxy would.

        F3 toggles the overlay and F4 cycles its panels, unless a sprite in the active scene has
        keyboard focus (is_active), so typing into text fields is never intercepted. Every other
        key goes to the active scene (every Scene has the handler, and records the press first),
        or to the game engine when there is no active scene.

        Args:
            event (KeyEvent): The key-down event.

        Raises:
            AttributeError: If there is no active scene and the game engine has no handler.

        """
        if event.key in OVERLAY_KEYS and not self._active_scene_has_focused_sprite():
            self.debug_overlay.handle_key(key=event.key)
            return
        if self.active_scene is not None:
            # Recorded before dispatch, so a quit-key release knows this scene saw the press
            self.active_scene.record_key_press(key=event.key)
            self.active_scene.on_key_down_event(event)
        elif self.game_engine is not None and hasattr(self.game_engine, 'on_key_down_event'):
            self.game_engine.on_key_down_event(event)
        else:
            message = (
                f"'{type(self)}' object has no attribute 'on_key_down_event': neither the "
                'active scene nor the game engine provides it'
            )
            raise AttributeError(message)

    def _present_frame(self: Self, *, full_update: bool) -> None:
        """Present the frame just run, unless the doors present frames themselves.

        A watched replay's frames are presented by its viewer's outer tick instead
        (``EngineSources.presents_frames``; ``_present_held_frame``).

        Args:
            full_update: True to flip the whole display (transitions); False to use the
                configured update type.

        """
        if active_sources().presents_frames:
            present_started_seconds = measured_seconds()
            self._show_frame(full_update=full_update)
            # Not the frame's processing time: a live window and a headless replay's dummy
            # display present at very different costs (glitchygames/replay/processing.py)
            self._frame_present_seconds += measured_seconds() - present_started_seconds
        else:
            # What this frame drew never reached the display: the next presented frame must
            # update all of it, not only its own dirty rects (an instant replay's first shown
            # frame after its fast-forward)
            self._display_is_stale = True

    def _show_frame(self: Self, *, full_update: bool) -> None:
        """Show the rendered frame, shifted by any active SCREEN shake and overlaid if shown.

        The display surface always holds the clean frame between presents: a shaken or overlaid
        frame is copied, shifted and drawn on for the flip, then restored. Dirty-rect rendering,
        screenshots and transition captures therefore never see the shift, the black strips,
        the debug overlay or the doors' own overlay (a watched replay's status bar, drawn last:
        ``EngineSources.draw_overlay``).

        Args:
            full_update: True to flip the whole display (transitions); False to use the
                configured update type.

        """
        if self.screen is not None:
            # Every presented frame is opaque: on a display with per-pixel alpha (cocoa) the
            # window shows alpha 0 as black, so a pixel copied from a surface carrying alpha 0
            # would be a black hole only on macOS (glitchygames/opacity.py, BUGS.md #142)
            make_opaque(surface=self.screen)
        # The overlay also draws during transitions (it reflects active_scene); captures stay clean
        offset_x, offset_y = self.screen_shake.offset
        pixel_offset = (round(offset_x), round(offset_y))
        overlay_visible = self.debug_overlay.is_visible
        sources = active_sources()
        # A watched replay draws its status bar on every frame, so its frames are copied and
        # flipped whole like frames with a visible debug overlay
        sources_draw_overlay = sources.draws_overlay
        if self.screen is not None and (
            pixel_offset != (0, 0) or overlay_visible or sources_draw_overlay
        ):
            clean_frame = self.screen.copy()
            # Copied back, never blended: on real video drivers (cocoa) the display has
            # per-pixel alpha, and a pixel below 255 would let the overlay show through
            clean_frame.set_alpha(None)
            if pixel_offset != (0, 0):
                self.screen.fill(SHAKE_BORDER_COLOR)
                self.screen.blit(clean_frame, pixel_offset)
            if overlay_visible and self.active_scene is not None:
                # A pause screen hands over the paused game, whose frozen picture it shows
                debug_subject = self.active_scene.debug_subject
                inspected_scene_label = (
                    None if debug_subject is self.active_scene else debug_subject.NAME
                )
                self.debug_overlay.draw(
                    self.screen,
                    scene=debug_subject,
                    screen_offset=pixel_offset,
                    frame_info=self._debug_frame_info(
                        shake_offset=(offset_x, offset_y),
                        inspected_scene_label=inspected_scene_label,
                    ),
                )
            if sources_draw_overlay:
                sources.draw_overlay(surface=self.screen)
            pygame.display.flip()
            self.screen.blit(clean_frame, (0, 0))
            self._display_is_stale = True
            return
        if self._display_is_stale:
            # The display still shows an older picture (the last shifted or overlaid frame, a
            # frame before unpresented ones, or the scene before a playback scope switched);
            # the surface holds the current one, so one full flip replaces it (a dirty-rect
            # update would not).
            self._display_is_stale = False
            pygame.display.flip()
            return
        if full_update:
            pygame.display.flip()
        else:
            self._update_display()

    @override
    def switch_to_scene(self: Self, next_scene: SceneInterface | None) -> None:
        """Switch to the next scene.

        The parameter keeps SceneInterface's signature, but the active scene must be a Scene
        (or None, which ends the run): the engine reads the attributes Scene declares.

        Args:
            next_scene (SceneInterface | None): The next scene to switch to: a Scene, or None.

        """
        scene = required_scene(next_scene=next_scene)
        if scene != self.active_scene:
            self.screen_shake.clear()  # Pause, game over and direct switches never inherit a shake
            self.rumble.clear_sustained()  # ...nor leave a controller buzzing
            # Track the previous scene BEFORE any cleanup or setup
            self.previous_scene = self.active_scene
            self._clear_outgoing_scene_pending_switch()
            self._reset_scene_timers()
            self._log_scene_switch(scene)
            self._cleanup_current_scene()
            self._activate_new_scene(scene)

    def _activate_new_scene(self: Self, scene: Scene | None) -> None:
        """Set a scene up and make it active (a switch, and a playback scope's rebuilt scene).

        Args:
            scene: The scene (None ends the run).

        """
        self._setup_new_scene(scene)
        self._log_blocked_events(scene)
        self.active_scene = scene
        self._configure_active_scene()
        self._track_scene_performance(scene)

    @staticmethod
    def _track_scene_performance(scene: Scene | None) -> None:
        """Tell the performance manager which scene its frames are now (real scenes only).

        Args:
            scene: The scene made active.

        """
        from glitchygames.performance import performance_manager

        if scene:  # Only track performance for real scenes, not None
            performance_manager.set_current_scene(scene.NAME)

    def _clear_outgoing_scene_pending_switch(self: Self) -> None:
        """Clear the pending switch of the scene being switched away from.

        Its pending switch has been honoured (or superseded by a transition): without this,
        a game that paused via next_scene would pause again one frame after resuming, and a
        scene left through a transition would switch back to a stale next_scene when it is
        returned to. The incoming scene's next_scene is left alone, because bootstrap scenes
        request their real scene from __init__.
        """
        if self.active_scene is not None:
            self.active_scene.next_scene = self.active_scene

    def _switch_to_requested_scene(self: Self) -> None:
        """Perform the plain scene switch the active scene requested via next_scene.

        Runs at the end of a frame, after rendering. A next_scene of None or of the active
        scene itself means no switch is pending.
        """
        if self.active_scene is None:
            return
        requested_scene = self.active_scene.next_scene
        if requested_scene is not None and requested_scene != self.active_scene:
            self.switch_to_scene(requested_scene)

    @override
    def play(self: Self) -> None:
        """Play the game."""
        return self.start()

    def _log_jitter_stats(self: Self, timer: object, wake_ns: int, deadline_ns: int) -> None:
        """Log timer jitter statistics if logging is enabled.

        Args:
            timer: The timer backend instance
            wake_ns: The actual wake time in nanoseconds
            deadline_ns: The target deadline in nanoseconds

        """
        # Cast timer to Any since it has dynamic methods (ns_now, etc.)
        timer_any: Any = timer
        try:
            jitter_ns = max(0, int(wake_ns - deadline_ns))
            # Log every fps_log_interval_ms
            interval_ns = int(float(self.fps_log_interval_ms) * 1_000_000)
            now_ns: int = timer_any.ns_now()
        except (ValueError, TypeError, AttributeError) as jitter_error:
            LOG.debug('Jitter logging error: %s', jitter_error)
            return
        buf = self._jitter_samples
        if not buf:
            # The first sample starts the first interval
            self._jitter_last_log_ns = now_ns
            self._jitter_interval_start_ns = now_ns
            self._jitter_late_frames = 0
        buf.append(jitter_ns)
        if len(buf) > JITTER_SAMPLE_BUFFER_MAX_SIZE:
            del buf[: len(buf) - JITTER_SAMPLE_BUFFER_MAX_SIZE]
        # Late frame if jitter > 0
        if jitter_ns > 0:
            self._jitter_late_frames += 1
        if now_ns - self._jitter_last_log_ns >= interval_ns:
            self._log_jitter_interval(buf, now_ns)

    def _log_jitter_interval(self: Self, buf: list[int], now_ns: int) -> None:
        """Log jitter statistics for the current interval and reset counters.

        Args:
            buf: Buffer of jitter sample values in nanoseconds
            now_ns: Current time in nanoseconds

        """
        data = sorted(buf)
        count = len(data)
        if count:
            p50 = data[int(0.50 * (count - 1))]
            p95 = data[int(0.95 * (count - 1))]
            p99 = data[int(0.99 * (count - 1))]
            p100 = data[-1]
            # Compute avg FPS and late-frame percentage over interval
            span_ns = max(1, now_ns - self._jitter_interval_start_ns)
            avg_fps = (count * 1_000_000_000) / span_ns
            late = self._jitter_late_frames
            late_pct = (late / count) * 100.0
            self.log.info(
                'Timer jitter ns: p50=%s p95=%s p99=%s max=%s frames=%s avg_fps=%.1f late=%.1f%%',
                p50,
                p95,
                p99,
                p100,
                count,
                avg_fps,
                late_pct,
            )
        self._jitter_last_log_ns = now_ns
        self._jitter_interval_start_ns = now_ns
        self._jitter_late_frames = 0

    def _handle_frame_pacing(
        self: Self,
        timer: object | None,
        period_ns: int,
        prev_deadline_ns: int | None,
        *,
        paced_seconds: float | None,
    ) -> None:
        """Handle frame pacing via timer or fallback to pygame clock.

        Only paces: the frame is measured afterwards, by _finish_frame, with
        time.perf_counter().

        Args:
            timer: The timer backend instance (or None)
            period_ns: Frame period in nanoseconds (0 if no timer)
            prev_deadline_ns: Previous frame deadline in nanoseconds (or None)
            paced_seconds: The doors' pacing for this frame (``paced_frame_seconds``): None
                paces to the target FPS, 0.0 (or less) never waits (no timer deadline and no
                clock tick: a headless replay), a positive period paces to it (``period_ns``
                already holds it for the timer backend; the pygame clock ticks at
                ``1 / paced_seconds``).

        """
        # Unpaced: a headless replay's frame times come from the recording, so waiting would
        # only take real time. Even the clock fallback below would wait (tick(target_fps) sleeps)
        if paced_seconds is not None and paced_seconds <= 0.0:
            return
        if timer is not None and period_ns > 0:
            # Cast timer to Any since it has dynamic methods (compute_deadline, etc.)
            timer_any: Any = timer
            deadline_ns: int = timer_any.compute_deadline(prev_deadline_ns, period_ns)
            wake_ns: int = timer_any.sleep_until_next(deadline_ns)
            self._timer_prev_deadline_ns = deadline_ns
            # Deadlines use the timer's own clock; the frame is NOT measured with it. The pygame
            # backend's ns_now() is whole milliseconds (get_ticks() * 1_000_000), so a true
            # 16.67 ms cadence would be measured as 17, 17, 16 ms (58.8, 58.8, 62.5 FPS).
            # _finish_frame measures with time.perf_counter() instead (BUGS.md #26).
            # Optional jitter logging
            if self.OPTIONS.get('log_timer_jitter', False):
                self._log_jitter_stats(timer, wake_ns, deadline_ns)
        elif timer is not None and paced_seconds is not None:
            # A positive paced period shorter than half a nanosecond rounds to a 0 ns period:
            # nothing to wait for. Never fall back to the pygame clock while a timer backend
            # paces the run (mixing the two clocks)
            pass
        # Fallback to pygame clock for FPS measurement if no timer
        elif paced_seconds is not None:
            self.clock.tick(1 / paced_seconds)
        elif self.target_fps > 0:
            self.clock.tick(self.target_fps)
        else:
            self.clock.tick()

    def _track_performance(self: Self, processing_time: float) -> None:
        """Feed this frame's FPS to the performance manager.

        Args:
            processing_time: Actual processing time in seconds

        """
        from glitchygames.performance import performance_manager

        # Deliberately NOT self.clock.get_fps(). pygame's Clock.get_fps():
        #   1. recomputes only every 10 tick() calls, so each value repeats for 10 frames,
        #   2. is 10000 / (milliseconds for the last 10 ticks), so values are quantized
        #      (357 = 10000/28, 385 = 10000/26, 500 = 10000/20, ...), and
        #   3. carries over from the previous scene (the clock is shared), so a new
        #      scene's first samples are stale.
        # The frame time _finish_frame measured with time.perf_counter() (the full
        # start-to-start period of the frame just finished), as the doors pass it on
        # (_performance_frame_seconds).
        performance_frame_seconds = self._performance_frame_seconds()
        current_fps = (1.0 / performance_frame_seconds) if performance_frame_seconds > 0 else 0.0
        performance_manager.track_fps_from_event(current_fps, processing_time)

    def start(self: Self) -> None:
        """Start the scene manager.

        Each frame starts at the previous frame's closing perf_counter() reading and ends in
        _finish_frame, which sets ``self.dt`` once, to that frame's start-to-start period, so
        logic in frame N receives the time frame N-1 took (engine audit #15).

        The blocking frame loop: ``begin_frames``, then ``run_frame_step`` while
        ``should_run_frames``, then ``end_frames``. An outer driver that must give control back
        between frames (a browser; glitchygames/host.py ``GameHost.run_async``) runs the same
        steps itself, one per tick, unpaced.
        """
        frame_start_seconds = self.begin_frames()
        while self.should_run_frames():
            frame_start_seconds = self.run_frame_step(frame_start_seconds=frame_start_seconds)
        self.end_frames()

    def begin_frames(self: Self) -> float:
        """Begin the run's frames: the frame clock's first reading and the first frame's dt.

        Returns:
            The perf_counter() reading the first frame starts at.

        """
        frame_start_seconds: float = time.perf_counter()
        self._previous_fps_event_seconds = frame_clock_seconds()
        # The first frame has no previous frame: its dt is the short time since the reading
        # above, as before (a replay's frame-time door returns the recorded first dt)
        self._set_frame_time(measured=time.perf_counter() - frame_start_seconds)
        mark_frames_started()
        return frame_start_seconds

    def should_run_frames(self: Self) -> bool:
        """Return True while a scene is active, no quit was requested and the doors go on.

        Returns:
            Whether the frame loop continues.

        """
        return (
            self.active_scene is not None
            and self.quit_requested is False
            and not active_sources().stop_requested
        )

    def run_frame_step(self: Self, *, frame_start_seconds: float, paced: bool = True) -> float:
        """Run one step of the frame loop: one frame, or a held frame presented again.

        Args:
            frame_start_seconds: The perf_counter() reading this frame starts at (the previous
                step's return value, or ``begin_frames``').
            paced: True (``start``) paces the frame as always: the timer backend's deadline,
                else the pygame clock, or the doors' pacing. False (an outer driver that waits
                for its own tick, ``GameHost.run_async``) never waits or calibrates a timer:
                the wait for the next tick is the pacing, and is measured into the next
                frame's start-to-start dt like a pacing sleep.

        Returns:
            The perf_counter() reading the next frame starts at.

        """
        # The doors may hold the loop between frames (a paused watched replay): no frame
        # runs, the last one is presented again with the doors' overlay
        self.last_step_was_held = active_sources().hold_frame()
        if self.last_step_was_held:
            # Unless the hold ended the run (the viewer quit): nothing more to show
            if not active_sources().stop_requested:
                self._present_held_frame()
            # The hold is not part of the next frame's measured time
            return time.perf_counter()

        # Frame pacing using timer backend when available
        # None without an engine (a bare SceneManager) or before the engine made its timer
        game_engine = self.game_engine
        timer = game_engine.timer if game_engine is not None and paced else None
        # The doors may pace the frame themselves (0.0: not at all, in a headless replay);
        # an unpaced step is never paced here
        paced_seconds = active_sources().paced_frame_seconds() if paced else 0.0
        period_ns = 0
        if timer is not None:
            period_ns = (
                timer.start_frame(self.target_fps)
                if paced_seconds is None
                else round(paced_seconds * 1_000_000_000)
            )

        self._run_frame()

        # The frame's processing time: its work, without the pacing sleep that follows
        processing_seconds = time.perf_counter() - frame_start_seconds

        return self._finish_frame(
            frame_start_seconds=frame_start_seconds,
            timer=timer,
            period_ns=period_ns,
            paced_seconds=paced_seconds,
            processing_seconds=processing_seconds,
        )

    def end_frames(self: Self) -> None:
        """End the run's frames: log why they ended and terminate the scene manager."""
        self._log_quit_info()
        self.terminate()

    def _present_held_frame(self: Self) -> None:
        """Present the latest frame while the doors hold the loop (a watched replay's outer tick).

        Nothing runs: no events are pumped (the doors read the viewer's keys in ``hold_frame``),
        no scene updates and the frame clock stands still. The display is flipped whole, with
        the debug overlay and the doors' overlay drawn on a copy as usual. The doors pace their
        holds (a watched replay's ``hold_frame`` sleeps until its viewer's next tick), so the
        loop does not spin.
        """
        self._show_frame(full_update=True)

    def _finish_frame(
        self: Self,
        *,
        frame_start_seconds: float,
        timer: object | None,
        period_ns: int,
        paced_seconds: float | None,
        processing_seconds: float,
    ) -> float:
        """End the frame: pace, measure it once, then record that one frame time.

        In order: pace (timer backend deadline on the timer's own clock, else the pygame
        clock; target 0 never sleeps, nor does a frame the doors leave unpaced) and log timer
        jitter; read time.perf_counter() once, which ends this frame and starts the next; set
        ``self.dt`` to the start-to-start period as the frame-time door returns it: the
        measurement when live, the recorded dt in a replay; add it to the frame clock; record
        it as the frame's FPS sample and post the FPS event when its interval of frame-clock
        time has passed (the frame clock replays exactly). Each frame's ``self.dt`` is set only
        here (_set_frame_time), so recorded frames sum exactly to elapsed time, and logic and the
        debug overlay in the next frame see the same value the statistics recorded (engine audit
        #15); the statistics take their frame time from _performance_frame_seconds, which is
        ``self.dt`` except in a ``--replay-fps real`` replay (this machine's measurement).

        The statistics are recorded after the closing reading, so their (microseconds of)
        work counts towards the next frame's period rather than going unmeasured.

        Args:
            frame_start_seconds: The perf_counter() reading this frame started at (the
                previous frame's closing reading).
            timer: The timer backend instance (or None).
            period_ns: Frame period in nanoseconds (0 if no timer or uncapped).
            paced_seconds: The doors' pacing for this frame (``paced_frame_seconds``, read when
                the frame started): None for the target FPS, 0.0 for none, else a period.
            processing_seconds: The frame's processing time, without pacing, in seconds.

        Returns:
            The closing perf_counter() reading: the next frame's start.

        """
        self._handle_frame_pacing(
            timer=timer,
            period_ns=period_ns,
            # The previous frame's deadline: only pacing sets it, after each frame's work
            prev_deadline_ns=self._timer_prev_deadline_ns,
            paced_seconds=paced_seconds,
        )

        closing_reading_seconds = time.perf_counter()
        self._set_frame_time(measured=closing_reading_seconds - frame_start_seconds)
        # The frame clock (glitchygames/sources.py) is the sum of closed frames' dt: UI timing and
        # FPS events use it, so they replay exactly
        advance_frame_clock(seconds=self.dt)

        self._track_performance(processing_time=processing_seconds)
        frame_clock = frame_clock_seconds()
        if self._should_post_fps_event(frame_clock, self._previous_fps_event_seconds):
            self._post_fps_event()
            self._previous_fps_event_seconds = frame_clock

        return closing_reading_seconds

    def _set_frame_time(self: Self, *, measured: float) -> None:
        """Set ``self.dt`` from a start-to-start measurement, through the frame-time door.

        The one writer of each frame's ``self.dt`` (start() for the first frame, _finish_frame
        for every later one); the measurement is kept for _performance_frame_seconds.

        Args:
            measured: The measured start-to-start time in seconds.

        """
        self._measured_frame_seconds = measured
        self.dt = active_sources().frame_seconds(measured=measured)

    def _performance_frame_seconds(self: Self) -> float:
        """The frame time FPS events, the performance manager and the debug overlay record.

        The one place the statistics get their frame time: the doors choose between the last
        measurement and ``self.dt`` (live play and a ``--replay-fps recorded`` replay use
        ``self.dt``, so a replay posts the recorded FPS; ``--replay-fps real`` uses the
        measurement; glitchygames/replay/driver.py).

        Returns:
            Seconds.

        """
        return active_sources().performance_frame_seconds(
            measured=self._measured_frame_seconds, frame_seconds=self.dt
        )

    def _run_frame(self: Self) -> None:
        """Run one frame (a transition frame or a scene frame), then end it at the doors.

        ``self.dt`` must already hold this frame's delta time. It is read before the frame
        runs and handed to the doors' ``end_frame`` as the frame's raw dt (a scene switch
        leaves the manager's ``self.dt`` alone: _reset_scene_timers resets only the scene
        timer). A transition's update receives it as is; scene
        logic and the camera aim receive it capped at the scene's MAX_FRAME_SECONDS
        (_scene_frame_seconds), which a replay re-derives from the scene class's attribute.
        The doors' ``end_frame`` (a recording samples the sprites there) runs after rendering,
        with the scene active at the end of the frame (after a switch, the new scene as set
        up), exactly as the golden-trace harness samples it.

        In-game playback (glitchygames/replay/playback.py): a requested scope is entered first,
        so its frame runs whole on the scoped doors. While a scope is in progress, an error in
        the frame (or in entering it) ends the scope: it is logged, the live game is restored,
        and the frame ends at the live doors. After ``end_frame`` the scope ends when its exit
        was requested or its recording ended or diverged. ``start()`` and the golden-trace
        harness share all of this.

        The instant-replay journal (glitchygames/instant_replay.py) begins or resumes at the
        top of the frame (``_begin_journal_frame``; inside a scope, a recorded resume is
        applied instead: ``_apply_resume_bridge``) and takes the frame after the doors ended
        it (``_journal_frame``).
        """
        self._frame_in_progress = True
        try:
            self._run_frame_steps()
        finally:
            self._frame_in_progress = False
        session = self._playback_session
        if session is not None and session.sources.end_reason is not None:
            self._exit_playback(reason=session.sources.end_reason)

    def _run_frame_steps(self: Self) -> None:
        """Run the frame and end it at the doors (``_run_frame``, with the frame in progress).

        The doors get the frame's processing time (glitchygames/replay/processing.py): its
        work from here to its end, without presenting it (``_present_frame``), without the
        doors' own ``end_frame`` and without the pacing that follows.
        """
        work_started_seconds = measured_seconds()
        self._frame_present_seconds = 0.0
        self._enter_requested_playback()
        self._apply_resume_bridge()
        self._begin_scene_logic_frame()
        self._begin_journal_frame()
        frame_dt = self.dt
        installed_frame_dt = self._installed_doors_frame_seconds(frame_dt=frame_dt)
        self._run_in_playback_scope(step=self._run_frame_contents)
        processing_seconds = measured_seconds() - work_started_seconds - self._frame_present_seconds
        session = self._playback_session
        if session is None:
            self._end_frame_at_doors(
                frame_dt=installed_frame_dt, processing_seconds=processing_seconds
            )
            self._journal_frame(frame_dt=frame_dt)
        else:
            scoped_sources = session.sources
            # Only the comparison is the scope's: an error of the installed doors (a session
            # recorder that cannot write) propagates as it would outside a scope
            self._run_in_playback_scope(
                step=lambda: scoped_sources.compare_frame(
                    frame_number=self.frame_number,
                    dt=frame_dt,
                    scene=self.active_scene,
                    control_events=self._frame_control_events,
                )
            )
            scoped_sources.base.end_frame(
                frame_number=self.frame_number,
                dt=installed_frame_dt,
                scene=self.active_scene,
                control_events=self._frame_control_events,
                processing_seconds=processing_seconds,
            )
        self._frame_control_events = []
        self.frame_number += 1

    def _installed_doors_frame_seconds(self: Self, *, frame_dt: float) -> float:
        """Return the frame time the installed doors gave this frame, for their ``end_frame``.

        Outside a playback scope it is the frame's dt. Inside one the frame runs with the
        played recording's dt, while the installed doors answered with the live frame time (or,
        in a replay of the session, its recorded one): a recording of the session must hold
        that, because the scope's first frame's time was read as the live frame before it
        ended and advanced the live frame clock and FPS event timer (BUGS.md #196;
        glitchygames/replay/playback.py, rule 5).

        Args:
            frame_dt: The frame's dt, read before the frame ran.

        Returns:
            Seconds.

        """
        session = self._playback_session
        if session is None:
            return frame_dt
        installed_frame_seconds = session.sources.installed_frame_seconds
        # Entering the scope asks its doors for the frame time (_enter_playback), and every
        # later frame's time is asked as the frame before it ends (_finish_frame)
        assert installed_frame_seconds is not None, 'the scope never asked for a frame time'
        return installed_frame_seconds

    def _begin_scene_logic_frame(self: Self) -> None:
        """Complete the active scene's start as its first logic frame begins (scene_start.py).

        At the top of a frame that will run the scene's logic (no transition plays), before
        any of its work: the streams, frame clock, FPS event timer and pending code-posted
        events are those the scene's logic begins with. Only the first such frame after the
        scene's setup counts (``SceneStartCapture.begin_first_logic_frame``).
        """
        if self._active_transition is not None:
            return
        if self.active_scene is None:
            return
        start_capture = self.active_scene.scene_start_capture
        if start_capture is not None:
            start_capture.begin_first_logic_frame(
                fps_event_seconds=self._previous_fps_event_seconds,
                earlier_internal_event_count=pending_code_post_count(),
            )

    def _enter_requested_playback(self: Self) -> None:
        """Enter the playback scope requested for this frame, if any (``request_playback``).

        A request made while a transition plays waits for the transition to end (the
        transition belongs to the live game, which the scope stashes). An error while entering
        is logged and undoes whatever was entered: the frame runs live.
        """
        request = self._requested_playback
        if (
            request is None
            or self._active_transition is not None
            or self._pending_transition is not None
        ):
            return
        self._requested_playback = None
        requesting_scene, self._playback_requesting_scene = self._playback_requesting_scene, None
        if self.active_scene is not requesting_scene:
            LOG.warning(
                'The %s playback was not started: the scene that asked for it has gone',
                request.kind,
            )
            return
        try:
            self._enter_playback(request=request)
        except Exception:
            LOG.exception('The %s playback could not start; the live game goes on', request.kind)
            self._exit_playback(reason='error')

    def _end_frame_at_doors(self: Self, *, frame_dt: float, processing_seconds: float) -> None:
        """Tell the active doors the frame ended (a recording writes it, a replay compares it).

        Args:
            frame_dt: The frame's raw dt, read before the frame ran.
            processing_seconds: The frame's processing time (``_run_frame_steps``).

        """
        active_sources().end_frame(
            frame_number=self.frame_number,
            dt=frame_dt,
            scene=self.active_scene,
            control_events=self._frame_control_events,
            processing_seconds=processing_seconds,
        )

    def _run_in_playback_scope(self: Self, *, step: Callable[[], None]) -> None:
        """Run part of a frame; inside a playback scope, an error in it ends the scope.

        Outside a scope the error propagates as always. Inside one (including while it is
        entered), it is logged, the scope ends (``_exit_playback``: the live game comes back
        untouched) and the frame goes on at the live doors.

        Args:
            step: The part of the frame.

        """
        if self._playback_session is None:
            step()
            return
        try:
            step()
        except Exception:
            LOG.exception('Playback failed; returning to the live game')
            self._exit_playback(reason='error')

    def _run_frame_contents(self: Self) -> None:
        """Run the frame itself: a transition frame or a scene frame (``_run_frame``)."""
        # During a transition, render the transition effect instead of the scene
        if self._active_transition is not None:
            transition_done = self._active_transition.update(self.dt)
            self._process_transition_events()
            self._run_supervisor_slot()
            self._update_frame_services()
            # A transition frame presents, so the display surface exists
            assert self.screen is not None
            self._active_transition.render(self.screen)
            self._present_frame(full_update=True)
            if transition_done:
                self._finalize_transition()
        else:
            self._run_scene_frame()

    def _enter_playback(self: Self, *, request: PlaybackRequest) -> None:
        """Begin a playback scope, between frames (glitchygames/replay/playback.py).

        Saves what the scope's end restores (the random streams, the frame clock, the FPS event
        timer, ``previous_scene``) and stashes the live scene without ``cleanup()``; pushes the
        scoped doors (before the rebuild, so the rebuilt scene opens sandboxed saves and captures
        its own start); sets the live rumble controller aside (rule 8 there); records the
        ``playback`` control event; rebuilds the scene from its start, which sets the streams and
        frame clock it began with; makes it active by the steps a switch takes
        (``_activate_new_scene``), with no shake or rumble carried in, and repeats a transition's
        arrival step for a scene that arrived by one
        (``_capture_arriving_scene``). Then this frame is its first logic frame
        (glitchygames/scene_start.py, rule 7): the streams, frame clock and FPS event timer are set
        as that frame began, its dt and the polled input before it come from the scoped doors (the
        recording's).

        Args:
            request: The scope to enter.

        Raises:
            RuntimeError: If no scene is active (there is no live game to return to).

        """
        live_scene = self.active_scene
        # Never None in a run: frames run only while a scene is active, and the scope is
        # entered only while the scene that asked for it is active (_enter_requested_playback)
        if live_scene is None:  # pragma: no cover - a guard for callers outside the frame loop
            message = f'A {request.kind} playback needs an active scene to return to'
            raise RuntimeError(message)
        session = request.begin_session(
            live_scene=live_scene,
            previous_scene=self.previous_scene,
            fps_event_seconds=self._previous_fps_event_seconds,
        )
        push_scoped_sources(sources=request.sources)
        # Events an earlier scope held and has not delivered yet (it ended into a scene that
        # started this one) belong to the live game: held again, ahead of this scope's own
        request.sources.held_live_events[:0] = take_redelivered_events()
        # From here on an error ends the scope and restores all of the above (_exit_playback)
        self._playback_session = session
        # The playback's rumble (its scene's pulses and shakes) goes to a controller of its own
        # that reaches no device (_update_frame_services), so the live game's waits untouched
        self._live_rumble_behind_scope = self.rumble
        self.rumble = RumbleController(intensity=self.rumble.intensity)
        self._scope_rumble_devices = ConnectedRumbleDevices()
        LOG.info('Starting the %s playback of %s', request.kind, request.scene_class.__name__)
        self.record_control_event(
            kind=PLAYBACK_KIND, data={'source': request.kind, 'frames': request.frame_count}
        )
        scene = rebuild_scene(
            start=request.start, scene_class=request.scene_class, options=self.OPTIONS
        )
        self._clear_frame_effects()
        # Made active by the steps a switch takes (the live scene is stashed, not cleaned up)
        self._reset_scene_timers()
        self._log_scene_switch(scene)
        self._activate_new_scene(scene)
        # The display shows the live scene: the playback's first presented frame updates all
        # of it
        self._display_is_stale = True
        first_logic_frame = request.first_logic_frame
        if first_logic_frame.arrived_by_transition:
            self._capture_arriving_scene()
        restore_stream_states(states=first_logic_frame.random_states)
        # The first played frame's logic polls what the recorded one did, not the live input
        self._restore_logic_frame_state(
            frame_clock_seconds=first_logic_frame.frame_clock_seconds,
            fps_event_seconds=first_logic_frame.fps_event_seconds,
            input_before=request.sources.replay.start_input,
        )
        self._set_frame_time(measured=self._measured_frame_seconds)
        # The live scene's instant-replay journal waits behind the scope and resumes on the
        # first frame after it (glitchygames/instant_replay.py, rule 7). Last, once entered:
        # a scope that fails to start leaves no gap to bridge
        journal = self._instant_replay_journal
        if journal is not None:
            journal.suspend()

    def _exit_playback(
        self: Self, *, reason: PlaybackEndReason, switches_to_then: bool = True
    ) -> None:
        """End the playback scope in progress and return to the live game (nothing if none).

        Keeps the replay's result (``last_playback_result``) and the outcome with ``reason``
        (``last_playback_outcome``); cleans up the playback's active scene (an error doing so is
        logged); then, whatever happened, removes the supervisors added during the scope, pops
        the scoped doors, restores the random streams, the
        frame clock, the FPS event timer, ``previous_scene`` and the live polled input (the
        installed doors' latest), and makes the stashed live scene active again without setting it
        up again (its snap mode, the event proxies, the caption and a full redraw), with no shake or
        rumble carried out. The events the scope held for the live game (its own posts, the player's
        releases, device and window events) are delivered before the next pump in the order they
        were pumped (``sources.redeliver_events``), unless the run is ending (dropped: no frame
        follows). A ``then`` other than the live scene is then switched to normally (the live scene
        is cleaned up as it is left), unless the run is ending.

        The frame that ends the scope still finishes afterwards (``_finish_frame``), so the
        restored live frame clock resumes one frame later: it advances by that frame's dt.

        Args:
            reason: Why the scope ends (``PlaybackOutcome.reason``).
            switches_to_then: False when the run is ending (``terminate``): the live scene is
                restored, to be torn down, and ``then`` is not set up.

        """
        session = self._playback_session
        if session is None:
            return
        self._playback_session = None
        result = session.sources.replay.result
        self._last_playback_result = result
        self._last_playback_outcome = session.outcome(reason=reason)
        LOG.info('The %s playback ended: %s', session.kind, reason)
        LOG.debug('%s', result.report())
        if reason == 'diverged' and result.divergence is not None:
            LOG.warning('%s diverged: %s', session.kind, result.divergence.describe())
        try:
            # The live scene is active only when the scope failed before its scene was
            if self.active_scene is not None and self.active_scene is not session.live_scene:
                self._cleanup_current_scene()
        except Exception:
            LOG.exception('The playback scene failed to clean up')
        finally:
            # A transition the playback started belongs to it (none of the live game's runs:
            # a scope begins only between transitions)
            self._active_transition = None
            self._pending_transition = None
            # Supervisors and handlers the scope's code added (its cleanup above included) end
            # with it (rule 4); the live ones stay
            self._remove_scope_supervision()
            pop_scoped_sources()
            restore_stream_states(states=session.saved_random_states)
            set_frame_clock_seconds(seconds=session.saved_frame_clock_seconds)
            self._previous_fps_event_seconds = session.saved_fps_event_seconds
            # The playback's own scene switches set it to playback scenes
            self.previous_scene = session.saved_previous_scene
            # _enter_playback set it right after the session, with nothing in between to fail
            assert self._live_rumble_behind_scope is not None
            self.rumble = self._live_rumble_behind_scope
            self._live_rumble_behind_scope = None
            self._clear_frame_effects()
            # The display shows the playback's last frame: the live scene's first presented
            # frame updates all of it, not only its own dirty rects
            self._display_is_stale = True
            set_current_input(snapshot=session.sources.last_base_snapshot)
            # In the order they were pumped; when the run ends no frame follows to deliver them
            if switches_to_then:
                redeliver_events(events=session.sources.held_live_events)
                # The playback scene's posts made after its frame's last pump (update(), its
                # event handlers, its cleanup above) are still queued: never the live game's.
                # The live doors' next read drops them, and they are no longer pending, so
                # nothing counts them as posted (a scene start's or resume bridge's earlier
                # events)
                scope_posts, queued_live_game_posts = self._forget_posts_still_pending(
                    session=session
                )
                # The live game's own supervisors' and handlers' posts are posted again, in
                # posting order: those the scope's pumps held, then those still queued (whose
                # queued copies are dropped like the scope's, so each arrives once). Pending
                # as the live scene resumes, they are what its journal's resume bridge counts
                # as earlier events (a later instant replay serves them, as no code of it
                # posts them)
                discard_scope_posts(posts=[*scope_posts, *queued_live_game_posts])
                live_game_posts().clear()
                # Each as it was posted: an input post (post_input_event) stays input
                for event, is_input in [
                    *session.sources.held_live_game_posts,
                    *(
                        (pygame.event.Event(*post), is_input_post(post=post))
                        for post in queued_live_game_posts
                    ),
                ]:
                    if is_input:
                        post_input_event(event)
                    else:
                        post_event(event)
            # Outside a scope every post is the live game's
            live_game_posts().clear()
            self._resume_live_scene(scene=session.live_scene)
        if switches_to_then and session.then is not session.live_scene:
            self.switch_to_scene(session.then)

    @staticmethod
    def _forget_posts_still_pending(
        *, session: PlaybackSession
    ) -> tuple[list[tuple[int, dict[str, Any]]], list[tuple[int, dict[str, Any]]]]:
        """Take the posts made inside a playback scope that no pump returned yet off the tracker.

        After the scope's first pump every pending post was made inside it (its pumps hold the
        live game's earlier posts and hand the rest to its replay): the scope's code's, or the
        live game's own supervisors' and handlers' (``recording.live_game_posts``: made in the
        frame that ends it, say right after ``end_playback()``). Before it, the live game's
        posts from before the scope come first; they stay pending, to arrive as usual.

        Args:
            session: The scope ending.

        Returns:
            The scope's code's posts and the live game's supervisors' and handlers' posts, each
            as (type, attributes), in posting order.

        """
        pending = pending_internal_posts()
        live_post_count = (
            0 if session.sources.has_pumped else len(session.sources.live_posts_before_scope)
        )
        posts_since_scope = pending[live_post_count:]
        del pending[live_post_count:]
        scope_posts = [post for post in posts_since_scope if not is_live_game_post(post=post)]
        queued_live_game_posts = [
            post for post in posts_since_scope if is_live_game_post(post=post)
        ]
        return scope_posts, queued_live_game_posts

    def _resume_live_scene(self: Self, *, scene: Scene) -> None:
        """Make a stashed scene active again as it was: no setup(), only what is drawn anew.

        Args:
            scene: The live scene a playback scope stashed.

        """
        self._log_scene_switch(scene)
        self.active_scene = scene
        self._activate_scene_snap_mode(scene)
        self._set_display_caption()
        self._setup_event_proxies()
        self._force_scene_redraw()
        self._redraw_scene_background()
        self._track_scene_performance(scene)

    def _clear_frame_effects(self: Self) -> None:
        """Stop the SCREEN shake and sustained rumble (a playback scope's start and end)."""
        self.screen_shake.clear()
        self.rumble.clear_sustained()

    def _run_scene_frame(self: Self) -> None:
        """Run one non-transition frame of the active scene.

        Starts the camera's frame, updates the scene, processes events, runs the supervisor
        slot (glitchygames/supervision.py), updates frame services, aims the camera, positions
        world sprites, renders the frame, advances the WORLD shake of a camera nothing moved,
        presents the frame, then starts a pending transition or performs a requested scene
        switch. ``self.dt`` must already hold this
        frame's delta time. The aim and the still-camera shake step are skipped when the
        active scene was switched mid-frame (during its logic or events, as resuming from the
        pause screen does): that scene ran no logic this frame, so its camera waits for its
        first dt_tick.
        """
        # Order matters: begin_frame() first, so a camera.update() the game made last frame
        # does not count as this frame's (the double-update warning in aim_camera). Then
        # Scene.dt_tick, events, the supervisor slot (after logic and events, so supervisors read
        # the frame's final logic state; before the aim and positioning, so what they change is
        # drawn this frame), frame services (shake and rumble, so positioning uses this
        # frame's WORLD shake offset), the camera aim and positioning, so sprites spawned in
        # dt_tick are placed before their first render. Scene.update() runs inside
        # _render_scene, after positioning.
        logic_scene = self.active_scene
        # A scene frame runs the active scene's logic (_update_scene): there is always one
        assert logic_scene is not None
        logic_scene.camera.begin_frame()
        # Logic and the camera aim share one (possibly capped) dt; self.dt stays the raw frame
        # time for the frame services, pacing and FPS statistics
        scene_dt = self._scene_frame_seconds()
        self._update_scene(scene_dt=scene_dt)
        self._process_events()
        self._run_supervisor_slot()
        self._update_frame_services()
        # A scene switched to during this frame (resuming from the pause screen switches while
        # events are processed) ran no logic this frame, so its camera is not aimed either:
        # camera time stays in step with the scene's dt_tick, as when games moved the camera
        # in dt_tick. Its world sprites are still positioned for this frame's render.
        if self.active_scene is logic_scene:
            self._aim_active_camera(scene_dt=scene_dt)
        # The display surface may appear only after startup; positioning needs its size
        self.update_screen()
        self._position_active_world_sprites()
        self._render_scene()
        # After the render phase, where game code may still call camera.update() (in update()):
        # a WORLD shake that nothing advanced this frame advances now, once, so it decays on a
        # camera that stands still (sprites drawn from it settle on the next frame)
        if self.active_scene is logic_scene:
            self._advance_still_camera_shake(scene_dt=scene_dt)
        self._present_frame(full_update=False)

        # Check for pending transition (set by Scene.transition_to)
        if self._pending_transition is not None:
            self._start_transition(*self._pending_transition)
            self._pending_transition = None
        # Check for plain scene switch (no transition, backward compatible)
        else:
            self._switch_to_requested_scene()

    def _active_camera(self: Self) -> Camera2D | None:
        """Return the active scene's camera, or None without an active scene.

        Every Scene has a camera; without an active scene the engine's camera steps are
        skipped.

        Returns:
            The active scene's Camera2D, or None when there is no active scene.

        """
        if self.active_scene is None:
            return None
        return self.active_scene.camera

    def _scene_frame_seconds(self: Self) -> float:
        """The dt the active scene's logic and camera aim receive this frame.

        self.dt, capped at the scene's MAX_FRAME_SECONDS when it sets one. After a hitch the
        scene advances at most the cap, while self.dt keeps the whole frame for pacing, FPS
        statistics and services.

        Returns:
            The scene's dt in seconds.

        """
        cap = self.active_scene.MAX_FRAME_SECONDS if self.active_scene is not None else None
        if cap is None:
            return self.dt
        return min(self.dt, cap)

    def _aim_active_camera(self: Self, *, scene_dt: float) -> None:
        """Aim the active scene's camera at its camera target (glitchygames.world.aim_camera).

        Called only while the scene whose logic ran this frame is still active.

        Args:
            scene_dt: The scene's dt this frame (_scene_frame_seconds).

        """
        scene = self.active_scene
        assert scene is not None
        aim_camera(scene=scene, camera=scene.camera, dt=scene_dt)

    def _advance_still_camera_shake(self: Self, *, scene_dt: float) -> None:
        """Advance the active camera's WORLD shake if nothing advanced it this frame.

        The shake advances when the camera moves (the engine aim or a game camera.update()).
        A camera nobody moved this frame (no follow target and no game update, or
        camera_target() returned None, as games do after game over) gets the advance here, with
        the dt the aim would have used, so the shake decays and its rumble stops instead of
        staying at full strength. Exactly one advance per frame in every case.

        Args:
            scene_dt: The scene's dt this frame (_scene_frame_seconds).

        """
        camera = self._active_camera()
        if camera is None or camera.shake_advanced_this_frame:
            return
        camera.advance_shake(dt=scene_dt)

    def _position_active_world_sprites(self: Self) -> None:
        """Place the active scene's world sprites on screen from its camera, and cull them.

        Screen-space sprites are untouched (glitchygames.world.position_world_sprites). Uses
        self.screen as it is (callers refresh it with update_screen() first): without a display
        surface there is nothing to place sprites on, so nothing is done.
        """
        camera = self._active_camera()
        if camera is None or self.screen is None:
            return
        assert self.active_scene is not None
        position_world_sprites(
            sprites=self.active_scene.all_sprites,
            camera=camera,
            screen_size=self.screen.get_size(),
        )

    def stop(self: Self) -> None:
        """Stop the game."""
        return self.terminate()

    @override
    def terminate(self: Self) -> None:
        """Terminate the scene manager.

        A playback scope in progress ends first (the live game comes back, so its scene is
        the one torn down) and a requested one is dropped.
        """
        self._requested_playback = None
        self._playback_requesting_scene = None
        self._exit_playback(reason='quit', switches_to_then=False)
        self._end_instant_replay_journal()
        self.switch_to_scene(None)

    def quit(self: Self) -> None:
        """Quit the game."""
        return self.quit_game()

    def quit_game(self: Self) -> None:
        """Quit the game."""
        # put a quit event in the event queue.
        self.log.info('POSTING QUIT EVENT')
        post_event(pygame.event.Event(pygame.QUIT, {}))

    def on_quit_event(self: Self, event: events.HashableEvent) -> None:  # ruff: ignore[unused-method-argument]
        """Handle quit events.

        Args:
            event (pygame.event.Event): The quit event.

        """
        # QUIT             none
        self.quit_requested = True

    def on_fps_event(self: Self, event: events.FpsEvent) -> None:
        """Handle FPS events.

        Args:
            event (FpsEvent): The event to handle.

        """
        # FPSEVENT is pygame.USEREVENT + 1
        if self.active_scene:
            self.active_scene.on_fps_event(event)

    def on_game_event(self: Self, event: events.GameEvent) -> None:
        """Handle game events.

        Args:
            event (GameEvent): The event to handle.

        """
        # GAMEEVENT is pygame.USEREVENT + 2
        # Call the event callback if it's registered.
        assert self.game_engine is not None
        try:
            event_subtype: int = getattr(event, 'subtype', 0)
            self.game_engine.registered_events[event_subtype](event)
        except KeyError:
            self.log.error(  # ruff: ignore[error-instead-of-exception]
                'Unregistered Event: %s '
                '(call self.register_game_event(<event subtype>, <event data>))',
                event,
            )

    def register_game_event(self: Self, event_type: int, callback: Callable[..., Any]) -> None:
        """Register a game event.

        Args:
            event_type (int): The event type to register.
            callback (Callable[..., Any]): The callback to call when the event is triggered.

        """
        assert self.game_engine is not None
        self.game_engine.register_game_event(event_type=event_type, callback=callback)

    # If the game hasn't hooked a call, we should check if the scene manager has.
    #
    # This will allow scenes to get pygame events directly, but we can still
    # hook those events in this engine, or in the subclassed game object, too.
    #
    # This allows maximum flexibility of event processing, with low overhead
    # at the expense of a slight layer violation.
    @override
    def __getattr__(self: Self, attr: str) -> Callable[..., Any]:
        """Proxy calls to the active scene.

        Args:
            attr (str): The attribute to proxy.

        Returns:
            Callable[..., Any]: The callable object.

        Raises:
            AttributeError: If the attribute is not an on_*_event method.

        """
        # Attempt to proxy the call to the active scene.
        if attr.startswith('on_') and attr.endswith('_event'):
            try:
                # Pass it to the active scene for handling
                return getattr(self.active_scene, attr)
            except AttributeError:
                # Pass it to the game engine for suppression
                return getattr(self.game_engine, attr)
        else:
            message = f"'{type(self)}' object has no attribute '{attr}'"
            raise AttributeError(message)

    def handle_event(self, event: events.HashableEvent) -> None:
        """Handle pygame events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # Check for focused sprites first
        if self.active_scene and self.active_scene.all_sprites:
            focused_sprites = [
                sprite
                for sprite in self.active_scene.all_sprites
                if hasattr(sprite, 'is_active') and sprite.is_active
            ]

            if focused_sprites and event.type == pygame.KEYDOWN:
                # Scene does not expose a handle_event() method; focused sprites
                # receive key events through the normal event dispatch pipeline.
                return

        # Only process other events if no focused sprites handled it
        if event.type == pygame.QUIT:
            self.log.info('POSTING QUIT EVENT')
            self.quit_requested = True

    def _should_post_fps_event(self, current_time: float, previous_fps_time: float) -> bool:
        """Check if FPS event should be posted.

        Args:
            current_time: Current time in seconds
            previous_fps_time: Previous FPS time in seconds

        Returns:
            True if FPS event should be posted

        """
        # Update FPS measurements at half the log interval for better accuracy
        # but still log at the specified interval
        update_interval_ms = float(self.OPTIONS['fps_log_interval_ms']) / 2.0
        return (current_time - previous_fps_time) * 1000 >= update_interval_ms

    def _post_fps_event(self) -> None:
        """Post FPS event."""
        # From the frame time alone, as _track_performance does: it comes through the doors
        # (_performance_frame_seconds), so a replay posts the recorded value (or, with
        # --replay-fps real, this machine's). Not self.clock.get_fps() for a zero frame time:
        # that is pygame's real-time pacing clock (and stale; see _track_performance), which a
        # replay cannot serve
        performance_frame_seconds = self._performance_frame_seconds()
        fps_value = 1.0 / performance_frame_seconds if performance_frame_seconds > 0 else 0.0

        post_event(pygame.event.Event(events.FPSEVENT, {'fps': fps_value}))

    def _update_scene(self, *, scene_dt: float) -> None:
        """Update the active scene.

        Args:
            scene_dt: The scene's dt this frame (_scene_frame_seconds).

        """
        assert self.active_scene is not None
        # Engine-owned, so a dt_tick override that skips super() still has game time
        self.active_scene.advance_game_time(seconds=scene_dt)
        self.active_scene.dt_tick(scene_dt)

    def _process_events(self) -> None:
        """Process game engine events."""
        if self.game_engine is not None:
            self.game_engine.process_events()

    def _process_transition_events(self) -> None:
        """Drain the event queue during a transition frame.

        Presses and motion (``TRANSITION_DISCARDED_EVENT_TYPES``) are discarded, so input
        pressed during a ride never acts when it ends; motion back to neutral is delivered
        (``is_discarded_during_transition``). Everything else goes through the normal
        GameEngine dispatch: releases (so held keys, including ActionMap state, are never left
        stuck), quit, window, focus and device events. ``_start_transition`` has already made
        the incoming scene the active scene, so the delivered events reach the scene that will
        be active after the transition; the outgoing scene has been cleaned up.
        """
        if self.game_engine is not None:
            self.game_engine.process_events(should_discard=is_discarded_during_transition)

    def _render_scene(self) -> None:
        """Render the active scene."""
        assert self.active_scene is not None
        # Update screen reference if needed
        self.update_screen()
        self.active_scene.update()
        if self.screen is not None:
            self.active_scene.render(self.screen)

    def _update_display(self) -> None:
        """Update the display based on update type."""
        assert self.active_scene is not None
        if self.update_type == 'update':
            # If no dirty rects, update the entire screen to show background
            if not self.active_scene.rects:
                pygame.display.update()
            else:
                pygame.display.update(self.active_scene.rects)
        elif self.update_type == 'flip':  # pragma: no branch - --update-type: update or flip
            pygame.display.flip()

    def _log_quit_info(self) -> None:
        """Log quit information."""
        self.log.info(
            'Game Quitting: Active Scene: %s, Quit Requested: %s',
            self.active_scene,
            self.quit_requested,
        )

    def _reset_scene_timers(self) -> None:
        """Reset the scene timer.

        The manager's ``dt`` is left alone: _set_frame_time is its only per-frame writer, and
        _configure_active_scene seeds the new scene's own ``dt``.
        """
        self.timer = 0

    def _log_scene_switch(self, next_scene: Scene | None) -> None:
        """Log scene switch information."""
        self.log.info('Switching to scene "%s" from scene "%s"', next_scene, self.active_scene)

    def _cleanup_current_scene(self) -> None:
        """Cleanup the current active scene."""
        if self.active_scene:
            self.active_scene._screenshot = self.active_scene.screenshot  # pyright: ignore[reportPrivateUsage]
            self.log.info('Cleaning up active scene %s.', self.active_scene)
            self.active_scene.cleanup()

    def _setup_new_scene(self, next_scene: Scene | None) -> None:
        """Set up the new scene.

        Every switch and transition (including resuming a paused scene) passes through here, so
        the incoming scene also forgets the key presses it recorded while it was last active.
        """
        if next_scene:
            self.log.info('Setting up new scene %s.', next_scene)
            # Ensure the new scene has access to the game engine (a bare SceneManager has none)
            if self.game_engine:
                next_scene.game_engine = self.game_engine  # type: ignore[attr-defined] # ty: ignore[invalid-assignment]
            # A press recorded before the scene was left (an ESC that paused it, released in
            # the pause scene) must not let a later release quit
            next_scene.forget_key_presses()
            # Complete the scene's start before its first setup() (a later setup, resuming it
            # from the pause screen, keeps the first); glitchygames/scene_start.py
            start_capture = next_scene.scene_start_capture
            if start_capture is not None:
                start_capture.complete(scene=next_scene)
            # Before setup(), so posts and the save stores setup() opens are seen
            self._prepare_instant_replay_journal(scene=next_scene)
            # The scene's snap mode is active from setup() on, so positions snapped while it
            # sets itself up (camera.snap_to, collision) use it, not the previous scene's mode
            self._activate_scene_snap_mode(next_scene)
            self._scene_in_setup = next_scene
            try:
                next_scene.setup()
            finally:
                self._scene_in_setup = None

    def _activate_scene_snap_mode(self, scene: Scene) -> None:
        """Make the scene's PIXEL_SNAP_MODE the default for sprites without their own mode.

        Every scene sets one (Scene's default is NEAREST_HALF_UP), so the previous scene's
        mode never leaks into it.

        Args:
            scene: The scene being activated.

        """
        set_active_default_snap_mode(scene.PIXEL_SNAP_MODE)

    def _log_blocked_events(self, next_scene: Scene | None) -> None:
        """Log the event types blocked when switching to the scene, on one line.

        One line, not one per type: a replay blocks dozens (glitchygames/replay/input_blocking.py).
        """
        if next_scene:
            blocked_event_names = [
                pygame.event.event_name(event_type)
                for event_type in events.ALL_EVENTS
                if pygame.event.get_blocked(event_type)
            ]
            self.log.info(
                'Scene %s blocked events: %s',
                next_scene.name,
                ', '.join(blocked_event_names) if blocked_event_names else 'None',
            )

    def _configure_active_scene(self) -> None:
        """Configure the active scene after switching."""
        if self.active_scene:
            # A new scene has not ticked yet; its first frame receives the real frame time
            self.active_scene.dt = 0.0
            self.active_scene.timer = self.timer  # type: ignore[attr-defined] # ty: ignore[invalid-assignment]
            # Don't call setup() here - it's already called in _setup_new_scene()

            self._set_display_caption()
            self.active_scene.load_resources()
            self._configure_scene_fps()
            self._log_scene_rendering_info()
            self._setup_event_proxies()
            self._force_scene_redraw()
            self._redraw_scene_background()
            self._apply_scene_fps()

    def _set_display_caption(self) -> None:
        """Set the display caption for the active scene."""
        assert self.active_scene is not None
        caption = ''

        if self.active_scene.NAME:
            caption = f'{self.active_scene.NAME}'

        if self.active_scene.VERSION:
            caption += f' v{self.active_scene.VERSION}'

        pygame.display.set_caption(caption, caption)

    def _configure_scene_fps(self) -> None:
        """Configure FPS for the scene."""
        assert self.active_scene is not None
        # Command line FPS takes precedence over scene FPS
        # Set the scene's target_fps to match the scene manager's target_fps
        # (which comes from OPTIONS)
        self.active_scene.target_fps = self.target_fps

    def _log_scene_rendering_info(self) -> None:
        """Log scene rendering information."""
        assert self.active_scene is not None
        fps_display = (
            'unlimited' if self.active_scene.target_fps == 0 else f'{self.active_scene.target_fps}'
        )
        self.log.info(
            'Rendering Scene "%s(%s)" at %s FPS',
            self.active_scene.NAME,
            type(self.active_scene),
            fps_display,
        )

    def _setup_event_proxies(self) -> None:
        """Set up event proxies for the scene."""
        # This controls how events are marshalled
        self.proxies = [self, self.active_scene]

    def _force_scene_redraw(self) -> None:
        """Force a scene redraw."""
        assert self.active_scene is not None
        self.active_scene.dirty = 1

    def _redraw_scene_background(self) -> None:
        """Redraw the scene background."""
        assert self.active_scene is not None
        # Update screen reference if needed
        self.update_screen()
        # Redraw the new scene's background to clear out any artifacts
        if self.screen is not None:
            self.screen.blit(self.active_scene.background, (0, 0))

    def _apply_scene_fps(self) -> None:
        """Apply scene-specific FPS configuration."""
        # Don't override the scene manager's target_fps with the scene's target_fps
        # The scene manager's target_fps comes from OPTIONS and should be maintained
        # The scene's target_fps is already set by _configure_scene_fps()


class Scene(SceneInterface, SpriteInterface, events.AllEventStubs):
    """Scene object base class.

    Subclass this to properly receive on_*_event() messages automatically.
    """

    log = LOG
    FPS = 0
    NAME = 'Unnamed Scene'
    VERSION = '0.0'
    # A game's preferred default target FPS (0.0 = uncapped); None uses the engine default.
    # An explicit --target-fps on the command line always wins.
    TARGET_FPS: ClassVar[float | None] = None
    # The longest frame time (seconds) this scene's dt_tick and camera aim receive; after a
    # hitch (a window drag, focus loss) they advance at most this much, so physics cannot
    # tunnel. None passes the real frame time. Pacing, FPS statistics and the frame services
    # (shake, rumble, the debug overlay) always see the real frame time.
    MAX_FRAME_SECONDS: ClassVar[float | None] = None
    # How sprites without their own pixel_snap_mode (and the camera and parallax layers) are
    # snapped to whole pixels while this scene runs.
    PIXEL_SNAP_MODE: ClassVar[PixelSnapMode] = PixelSnapMode.NEAREST_HALF_UP
    # False for a scene that cannot be rebuilt on its own from replay_arguments() (PauseScene
    # presents another scene): its start is never captured (glitchygames/scene_start.py)
    CAPTURES_SCENE_START: ClassVar[bool] = True
    # Seconds an instant replay of this scene shows, or None for no instant replay. Set, the
    # scene manager keeps the scene's frames in memory from its start (glitchygames/
    # instant_replay.py) and its start is captured in plain live play too
    INSTANT_REPLAY_SECONDS: ClassVar[float | None] = None
    # The most scene time an instant replay re-simulates from the scene's start before the
    # seconds it shows (plans/2026-10-19-gameplay-replay.md, section 5.4)
    MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS: ClassVar[float] = 60.0
    # True on a game's scene class (the one given to GameEngine) to receive the window system's
    # raw messages (SYSWMEVENT) in on_sys_wm_event; blocked by default, as SDL leaves them.
    # See allow_every_event_type in glitchygames/events/base.py
    NATIVE_WINDOW_MESSAGES: ClassVar[bool] = False

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the scene.

        Args:
            options (dict[str, Any] | None): The options passed to the game.
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups.

        """
        # First, before anything (a subclass's body after super().__init__() included) draws
        # random numbers: the streams and frame clock this scene began with, when its start is
        # captured (None otherwise; glitchygames/scene_start.py)
        self.scene_start_capture: SceneStartCapture | None = begin_scene_start_capture(
            scene_class=type(self)
        )

        if options is None:
            options = {'debug_events': False, 'no_unhandled_events': False}

        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        if self.NAME == 'Unnamed Scene':
            self.NAME = type(self).__name__  # pyright: ignore[reportConstantRedefinition]

        super().__init__()

        # Since SceneManager is a singleton, this will ensure that
        # any non-active scene which gets initialized will simply
        # get a copy of the scene manager, rather than overwriting
        # the active scene.
        #
        # This helps us keep the upper layers clean by not requiring
        # new scenes to care about the SceneManager when being
        # instantiated.
        self.target_fps: float = 0.0
        self.fps: float = 0.0
        self.dt: float = 0.0
        self.dt_timer: float = 0.0
        self.tweens: TweenManager = TweenManager()
        self.collisions: CollisionManager = CollisionManager()
        self.dirty = 1
        self.options = options
        self.scene_manager = SceneManager()
        self.name = type(self)
        self._background_color: tuple[int, ...] | None = None
        self._background_pattern: BackgroundPattern | None = None
        self._last_fps_log_time: float = 0.0
        self._screenshot: pygame.Surface | None = None
        self.quit_requested: bool = False
        # Keys whose key-down reached this scene and are not yet released (record_key_press)
        self._keys_pressed_in_scene: set[int] = set()
        self._world_shake_warning_logged: bool = False
        # Logic seconds since this scene started (game_time); the scene manager adds each
        # frame's scene dt before dt_tick
        self._game_time_seconds: float = 0.0
        self.next_scene: Scene | Self | None = self
        self.rects = None
        self.screen = pygame.display.get_surface()
        assert self.screen is not None
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        # Identity camera for scenes that do not scroll (apply(x, y) returns (x, y)); scrolling
        # games replace it with their own. Never None, so callers need no guards.
        self.camera: Camera2D = Camera2D(
            screen_width=self.screen_width, screen_height=self.screen_height
        )

        # http://n0nick.github.io/blog/2012/06/03/quick-dirty-using-pygames-dirtysprite-layered/
        self.all_sprites = groups

        # Initial screen state.

        self.screen = pygame.display.get_surface()
        assert self.screen is not None
        # In the display's format (BUGS.md #143: convert() returns the converted surface)
        self.background = pygame.Surface(self.screen.get_size()).convert()
        # A scene that sets no background shows the default pattern (glitchygames/backgrounds.py)
        # instead of black, which cannot be told from "nothing rendered"
        self.background_pattern = active_default_background_pattern()

        # This allows us to be treated like a sprite
        self.image = self.screen
        self.rect = self.screen.get_rect()

        self.dirty = 1

    @property
    def debug_subject(self: Self) -> Scene:
        """The scene the debug overlay inspects: normally this scene itself.

        A scene that only presents another scene (PauseScene shows a frozen screenshot of the
        paused game) returns that scene, so its hitboxes and physics stay visible and line up
        with the frozen picture.
        """
        return self

    @property
    def scene_start(self: Self) -> SceneStart | None:
        """How this scene began, once set up (glitchygames/scene_start.py).

        None when its start was not captured (live play without recording, playback or
        instant replay) or before its first setup.
        """
        if self.scene_start_capture is None:
            return None
        return self.scene_start_capture.start

    def replay_arguments(self: Self) -> dict[str, Any]:
        """Return the constructor arguments that rebuild this scene as it began (besides options).

        A scene rebuilt for playback is ``type(scene)(**replay_arguments(), options=...)``
        (glitchygames/scene_start.py), so a scene built with arguments carried from the
        previous scene (a floor's score and lives) returns them as they were when it was built.
        They must read back from JSON exactly as returned. Asked once, before the scene's first
        setup, and only while its start is captured.

        Returns:
            The arguments by name; none by default.

        """
        return {}

    @property
    def input_devices(self: Self) -> InputDevices:
        """Every joystick and game controller the game sees, by instance id.

        Each ``InputDevice`` reads the frame's input snapshot on its joystick layer and, for a
        mapped pad, its controller layer; its events reach ``on_*_event`` from one layer only
        (glitchygames/input/input_devices.py). Empty without an engine.
        """
        return self.scene_manager.input_devices

    def on_input_device_added(self: Self, *, device: InputDevice) -> None:
        """Called while this scene is active when a device is connected; nothing by default.

        Args:
            device: The device (``input_devices`` holds it already).

        """

    def on_input_device_removed(self: Self, *, device: InputDevice) -> None:
        """Called while this scene is active when a device is disconnected; nothing by default.

        Args:
            device: The device (``input_devices`` no longer holds it).

        """

    @property
    def game_time(self: Self) -> float:
        """Logic seconds since this scene started: the sum of the dt its dt_tick received.

        Capped by MAX_FRAME_SECONDS where set, and it does not advance while the scene is not
        running (paused, or switched away), so cooldowns and timers measured with it pause with
        the game and replay exactly. Use it for gameplay timing instead of the wall clock.
        """
        return self._game_time_seconds

    def advance_game_time(self: Self, *, seconds: float) -> None:
        """Add one frame's scene dt to game_time.

        The engine calls this once per scene frame (SceneManager._update_scene, before
        dt_tick); games read game_time and never call it. It is public only because the scene
        manager, another class, calls it.

        Args:
            seconds: The scene's (possibly capped) dt this frame.

        """
        self._game_time_seconds += seconds

    @property
    def screenshot(self: Self) -> pygame.Surface:
        """A screenshot of the scene.

        Returns:
            pygame.Surface: The scene screenshot.

        """
        assert self.screen is not None
        # In the display's format (BUGS.md #143: convert() returns the converted surface)
        screenshot = pygame.Surface((self.screen_width, self.screen_height)).convert()
        # Opaque black, then the channel-wise maximum with the screen: its red, green and blue
        # are copied unblended and every pixel stays opaque, as the presented frame shows them
        # (glitchygames/opacity.py). A plain blit would blend away colours under alpha 0, and on
        # a display with per-pixel alpha (cocoa) leave alpha 0 behind: a black screenshot
        # (BUGS.md #142)
        screenshot.fill(BLACK)
        screenshot.blit(self.screen, (0, 0), special_flags=pygame.BLEND_RGBA_MAX)
        return screenshot

    @property
    def background_color(self: Self) -> tuple[int, ...] | None:
        """The background color.

        Returns:
            tuple[int, ...] | None: The background color, or None while the background is a
            pattern (background_pattern).

        """
        return self._background_color

    @background_color.setter
    def background_color(self: Self, new_color: tuple[int, ...]) -> None:
        """Set the background color.

        The background is the frame's bottom layer, so it is opaque: an RGB colour is
        normalized to RGBA with alpha 255. A translucent colour is refused: nothing is under the
        background to show through it, so the dummy and x11 drivers would show it opaque while
        cocoa, whose display has per-pixel alpha, shows alpha 0 as black (BUGS.md #142).

        Args:
            new_color (tuple[int, ...]): The new background color (RGB, or RGBA with alpha 255).

        Raises:
            ValueError: The colour is translucent, or has neither three nor four components.

        """
        if len(new_color) == RGB_COMPONENT_COUNT:
            new_color = (*new_color, OPAQUE)
        if len(new_color) != RGBA_COMPONENT_COUNT:
            message = f'A scene background colour is RGB or RGBA, not {new_color!r}'
            raise ValueError(message)
        if new_color[-1] != OPAQUE:
            message = (
                f'A scene background colour must be opaque: {new_color!r} has alpha '
                f'{new_color[-1]}, and nothing is under the background to show through it'
            )
            raise ValueError(message)
        self._background_color = new_color
        self._background_pattern = None
        assert self._background_color is not None
        assert self.screen is not None
        self.background.fill(self._background_color)
        self.all_sprites.clear(self.screen, self.background)

    @property
    def background_pattern(self: Self) -> BackgroundPattern | None:
        """The built-in pattern the background shows (glitchygames/backgrounds.py).

        A scene that sets no background gets the active default pattern (the TV test
        pattern unless --default-background chose another).

        Returns:
            BackgroundPattern | None: The pattern, or None while the background is a colour
            (background_color).

        """
        return self._background_pattern

    @background_pattern.setter
    def background_pattern(self: Self, new_pattern: BackgroundPattern) -> None:
        """Show a built-in pattern as the background (it replaces any background colour).

        Args:
            new_pattern: The pattern.

        """
        self._background_pattern = new_pattern
        self._background_color = None
        assert self.screen is not None
        self.background.blit(
            background_pattern_surface(pattern=new_pattern, size=self.background.get_size()),
            (0, 0),
        )
        self.all_sprites.clear(self.screen, self.background)

    def transition_to(self: Self, next_scene: Scene | None, transition: Transition) -> None:
        """Switch to another scene with a visual transition effect.

        Args:
            next_scene: The scene to transition to.
            transition: A Transition object (FadeTransition, SlideTransition, etc.).

        """
        self.scene_manager.request_transition(next_scene, transition)

    def setup(self: Self) -> None:
        """Set up the scene."""

    def cleanup(self: Self) -> None:
        """Cleanup the scene."""

    def shake(self: Self, shake: Shake, *, targets: ShakeTarget = ShakeTarget.WORLD) -> None:
        """Start a shake on the world (camera), the whole screen, or both.

        Rumble, if the shake has it, is sent automatically by the scene manager.

        Args:
            shake: The shake to start.
            targets: ShakeTarget.WORLD, ShakeTarget.SCREEN, or both combined with |.

        Raises:
            RuntimeError: If WORLD is requested on a scene that is not active (for example
                from a transition cue, which runs after the scene was cleaned up).

        """
        if ShakeTarget.WORLD in targets:
            if self.scene_manager.active_scene is not self:
                message = f'{self.NAME} is not the active scene; use ShakeTarget.SCREEN'
                raise RuntimeError(message)
            self.camera.shake_effect.add(shake)
            if not self._world_shake_warning_logged and not self._world_shake_moves_anything():
                LOG.warning(
                    'WORLD shake on %s has no effect: no sprites are positioned through its '
                    'camera; use ShakeTarget.SCREEN',
                    self.NAME,
                )
                self._world_shake_warning_logged = True
        if ShakeTarget.SCREEN in targets:
            self.scene_manager.screen_shake.add(shake)

    def _world_shake_moves_anything(self: Self) -> bool:
        """Whether a WORLD shake on this scene's camera would move anything on screen.

        It does when a sprite is positioned through Camera2D.apply(), when the camera scrolls
        background layers, or when the scene has world sprites (the engine places them from
        the camera, shake included, without apply()). Decided when shake() is called.

        The warning only has to ask whether anything is drawn from the camera: whether the
        camera moves does not matter, because the engine advances a WORLD shake every frame
        even on a camera nothing moves (SceneManager._advance_still_camera_shake), so on a
        scene with world sprites it always shakes them and then decays.

        Returns:
            True if anything is drawn from this scene's camera.

        """
        return (
            self.camera.has_been_applied
            or self.camera.has_parallax_layers
            or any(is_world_positioned(sprite) for sprite in self.all_sprites)
        )

    def camera_target(self: Self) -> tuple[float, float] | None:
        """The world point the engine aims the camera at this frame, or None (manual camera).

        Override to aim the camera anywhere (a point between two players, a cutscene focus).
        The default returns the camera's follow target position (Camera2D.follow()). The
        engine applies the camera's follow axes to whatever point this returns.

        Returns:
            tuple[float, float] | None: The target's (world_x, world_y), or None when the
                camera follows nothing.

        """
        target = self.camera.follow_target
        if target is None:
            return None
        # Camera2D.follow() checked that the target has world_x and world_y
        return (float(target.world_x), float(target.world_y))

    def apply_camera_to_sprites(self: Self) -> None:
        """Reposition camera-relative sprites from the current camera.

        Default: nothing. Games that place sprites through Camera2D.apply() override this so
        the scene manager can refresh positions (for example, after clearing a WORLD shake
        before a transition screenshot).
        """

    def dt_tick(self: Self, dt: float) -> None:
        """Update the scene's delta time and active tweens.

        Args:
            dt (float): The delta time to update.

        """
        self.dt = dt
        self.dt_timer += self.dt
        self.tweens.update(dt)

    @override
    def update(self: Self) -> None:
        """Update the active scene."""
        # Tweak to enable compound sprites to manage their own subsprites dirty states
        #
        # Ideally we'd just make dirty a property with a setter and getter on each
        # sprite object, but that doesn't work for some reason.
        [sprite.update_nested_sprites() for sprite in self.all_sprites]

        # Update all sprites that are dirty
        [sprite.update() for sprite in self.all_sprites if sprite.dirty]

        # Make all of the new scene's sprites dirty to force a redraw
        if self.dirty:
            for sprite in self.all_sprites:
                sprite.dirty = 1 if not sprite.dirty else sprite.dirty

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Render the active scene.

        Args:
            screen (pygame.Surface): The screen to render to.

        """
        # Use LayeredDirty's clear method for proper background clearing and dirty rect management
        self.all_sprites.clear(screen, self.background)
        self.rects = self.all_sprites.draw(screen)

    def sprites_at_position(self: Self, pos: tuple[int, int]) -> list[Any]:
        """Return the sprites at a given position.

        Args:
            pos (tuple[int, int]): The position to check.

        Returns:
            list[Any]: The sprites at the given position.

        """
        mouse = MousePointer(pos=pos)

        return pygame.sprite.spritecollide(sprite=mouse, group=self.all_sprites, dokill=False)

    def _get_collided_sprites(self, position: tuple[int, int]) -> list[Any]:
        """Get sprites at the given position.

        Args:
            position: The position to check for sprites

        Returns:
            List of sprites at the position

        """
        return self.sprites_at_position(pos=position)

    def _get_focusable_sprites(self, collided_sprites: list[Any]) -> list[Any]:
        """Get focusable sprites from the collided sprites.

        Args:
            collided_sprites: List of sprites that were collided with

        Returns:
            List of focusable sprites

        """
        return [s for s in collided_sprites if hasattr(s, 'focusable') and s.focusable]

    def _get_focused_sprites(self) -> list[Any]:
        """Get currently focused sprites.

        Returns:
            List of currently focused sprites

        """
        return [
            sprite
            for sprite in self.all_sprites
            if hasattr(sprite, 'is_active') and sprite.is_active
        ]

    def _has_focusable_sprites(self, collided_sprites: list[Any]) -> bool:
        """Check if any of the collided sprites are focusable.

        Args:
            collided_sprites: List of sprites that were collided with

        Returns:
            True if any sprite is focusable, False otherwise

        """
        return any(hasattr(sprite, 'focusable') and sprite.focusable for sprite in collided_sprites)

    def _unfocus_sprites(self, focused_sprites: list[Any]) -> None:
        """Unfocus the given sprites.

        Args:
            focused_sprites: List of sprites to unfocus

        """
        # Every focused sprite has is_active (_get_focused_sprites)
        for sprite in focused_sprites:
            self.log.debug('Unfocusing %s', type(sprite).__name__)
            sprite.is_active = False
            if hasattr(sprite, 'on_focus_lost'):
                sprite.on_focus_lost()

    def _handle_focus_management(self, collided_sprites: list[Any]) -> None:
        """Handle focus management for mouse clicks.

        Args:
            collided_sprites: List of sprites that were collided with

        """
        focused_sprites = self._get_focused_sprites()

        # If we clicked outside all sprites that can be focused, unfocus them
        if not self._has_focusable_sprites(collided_sprites):
            self.log.debug('Click outside focusable sprites - unfocusing')
            self._unfocus_sprites(focused_sprites)

    def record_key_press(self: Self, *, key: int) -> None:
        """Note that a key-down reached this scene.

        SceneManager calls this for every key-down it routes to the active scene, before the
        scene's own on_key_down_event, so subclasses that override that handler are covered.
        on_key_up_event quits only on the release of a key recorded here. Games never call it;
        it is public only because the scene manager, another class, calls it.

        Args:
            key: The pygame key code.

        """
        self._keys_pressed_in_scene.add(key)

    def forget_key_presses(self: Self) -> None:
        """Forget every key press recorded by record_key_press.

        SceneManager calls this whenever the scene becomes active (switched to, resumed, or
        the target of a transition), before setup(). A press whose release went to another
        scene would otherwise stay recorded, and a later release of that key (whose press was
        discarded during a transition) would quit.
        Games never call it; it is public only because the scene manager calls it.
        """
        self._keys_pressed_in_scene.clear()

    def _handle_quit_key_press(self) -> None:
        """Handle quit key press when no sprites are focused."""
        self.log.info('Quit requested')
        # Post a QUIT event to ensure proper cleanup
        post_event(pygame.event.Event(pygame.QUIT))

    @override
    def on_audio_device_added_event(self: Self, event: events.AudioDeviceEvent) -> None:
        """Handle audio device added events.

        Args:
            event (AudioDeviceEvent): The event to handle.

        """
        # AUDIODEVICEADDED which, iscapture
        self.log.debug('%s: On Audio Device Added Event %s', type(self), event)

    @override
    def on_audio_device_removed_event(self: Self, event: events.AudioDeviceEvent) -> None:
        """Handle audio device removed events.

        Args:
            event (AudioDeviceEvent): The event to handle.

        """
        # AUDIODEVICEREMOVED which, iscapture
        self.log.debug('%s: On Audio Device Removed Event %s', type(self), event)

    @override
    def on_controller_button_down_event(self: Self, event: events.ControllerButtonEvent) -> None:
        """Handle controller button down events.

        Args:
            event (ControllerButtonEvent): The event to handle.

        """
        # CONTROLLERBUTTONDOWN which, button
        self.log.debug('%s: On Controller Button Down Event %s', type(self), event)

    @override
    def on_controller_button_up_event(self: Self, event: events.ControllerButtonEvent) -> None:
        """Handle controller button up events.

        Args:
            event (ControllerButtonEvent): The event to handle.

        """
        # CONTROLLERBUTTONUP which, button
        self.log.debug('%s: On Controller Button Up Event %s', type(self), event)

    @override
    def on_joy_button_down_event(self: Self, event: events.JoyButtonEvent) -> None:
        """Handle joy button down events.

        Args:
            event (JoyButtonEvent): The event to handle.

        """
        # JOYBUTTONDOWN    joy, button
        self.log.debug('%s: On Joy Button Down Event %s', type(self), event)

    @override
    def on_joy_button_up_event(self: Self, event: events.JoyButtonEvent) -> None:
        """Handle joy button up events.

        Args:
            event (JoyButtonEvent): The event to handle.

        """
        # JOYBUTTONUP      joy, button
        self.log.debug('%s: On Joy Button Up Event %s', type(self), event)

    @override
    def on_key_up_event(self, event: events.KeyEvent) -> None:
        """Handle key up events.

        Args:
            event (KeyEvent): The event to handle.

        """
        self.log.debug('%s: On Key Up Event %s', type(self), event)

        # Check for focused sprites first
        focused_sprites = self._get_focused_sprites()

        # Only a release whose press this scene received can quit (record_key_press): a key
        # pressed during a transition (the press is discarded) or in a scene that has since
        # been left must not quit from here. Each release consumes its press.
        event_key: int | None = getattr(event, 'key', None)
        was_pressed_in_scene = event_key is not None and event_key in self._keys_pressed_in_scene
        if event_key is not None:  # pragma: no branch - a key release always has a key
            self._keys_pressed_in_scene.discard(event_key)

        # Only process quit keys if no sprites are focused
        if (
            not focused_sprites
            and was_pressed_in_scene
            and event_key in {pygame.K_q, pygame.K_ESCAPE}
        ):
            self._handle_quit_key_press()

    @override
    def on_menu_item_event(self: Self, event: events.HashableEvent) -> None:
        """Handle menu item events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # MENUITEM         menu, item
        self.log.debug('%s: On Menu Item Event %s', type(self), event)

    @override
    def on_mouse_button_down_event(self: Self, event: events.MouseButtonEvent) -> None:
        """Handle mouse button down events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        self.log.debug('=== Scene: Mouse Button Down ===')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        self.log.debug('Click position: %s', event_pos)

        # Get sprites at click position
        collided_sprites = self._get_collided_sprites(event_pos)
        self.log.debug('Collided sprites: %s', [type(s).__name__ for s in collided_sprites])
        focusable_sprites = self._get_focusable_sprites(collided_sprites)
        self.log.debug('Focusable sprites: %s', focusable_sprites)

        # Diagnostics: log the top-most collided sprite and its active state
        if collided_sprites:
            top_sprite = collided_sprites[-1]
            self.log.debug(
                'Top sprite @ DOWN: %s, active=%s, pos=%s',
                type(top_sprite).__name__,
                getattr(top_sprite, 'active', None),
                event_pos,
            )

        # Find currently focused sprites
        focused_sprites = self._get_focused_sprites()
        self.log.debug('Currently focused sprites: %s', [type(s).__name__ for s in focused_sprites])

        # Handle focus management
        self._handle_focus_management(collided_sprites)

        # Process the click for collided sprites
        for sprite in collided_sprites:
            if hasattr(sprite, 'on_mouse_button_down_event'):
                sprite.on_mouse_button_down_event(event)

    @override
    def on_mouse_drag_event(self: Self, event: events.MouseMotionEvent, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.debug('%s: Mouse Drag Event: %s %s', type(self), event, trigger)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        # Optimized: Skip expensive collision detection for drag events
        # Most drag handling is done by specific sprite drag handlers
        # (e.g., on_left_mouse_drag_event)
        # Only do collision detection if specifically needed
        collided_sprites = self.sprites_at_position(pos=event_pos)

        # Diagnostics: log the top-most collided sprite and its active state during drag
        if collided_sprites:
            top_sprite = collided_sprites[-1]
            self.log.debug(
                'Top sprite @ DRAG: %s, active=%s, pos=%s',
                type(top_sprite).__name__,
                getattr(top_sprite, 'active', None),
                event_pos,
            )

        for sprite in collided_sprites:
            sprite.on_mouse_drag_event(event, trigger)

    @override
    def on_mouse_drop_event(self: Self, event: events.MouseButtonEvent, trigger: object) -> None:
        """Handle mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.debug('%s: Mouse Drop Event: %s %s', type(self), event, trigger)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_mouse_drop_event(event, trigger)

    @override
    def on_left_mouse_drag_event(
        self: Self, event: events.MouseMotionEvent, trigger: object
    ) -> None:
        """Handle left mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.debug('%s: Left Mouse Drag Event: %s %s', type(self), event, trigger)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites: list[Any] | None = self.sprites_at_position(pos=event_pos)

        if collided_sprites:
            collided_sprites[-1].on_left_mouse_drag_event(event, trigger)

    @override
    def on_left_mouse_drop_event(
        self: Self, event: events.MouseButtonEvent, trigger: object
    ) -> None:
        """Handle left mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.debug('%s: Left Mouse Drop Event: %s %s', type(self), event, trigger)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_left_mouse_drop_event(event, trigger)

    @override
    def on_middle_mouse_drag_event(
        self: Self,
        event: events.MouseMotionEvent,
        trigger: object,
    ) -> None:
        """Handle middle mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.info('%s: Middle Mouse Drag Event: %s %s', type(self), event, trigger)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_drag_event(event, trigger)

    @override
    def on_middle_mouse_drop_event(
        self: Self,
        event: events.MouseButtonEvent,
        trigger: object,
    ) -> None:
        """Handle middle mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.info('%s: Middle Mouse Drop Event: %s %s', type(self), event, trigger)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_drop_event(event, trigger)

    @override
    def on_right_mouse_drag_event(
        self: Self, event: events.MouseMotionEvent, trigger: object
    ) -> None:
        """Handle right mouse drag events.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.info('%s: Right Mouse Drag Event: %s %s', type(self), event, trigger)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_drag_event(event, trigger)

    @override
    def on_right_mouse_drop_event(
        self: Self, event: events.MouseButtonEvent, trigger: object
    ) -> None:
        """Handle right mouse drop events.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (object): The event trigger.

        """
        self.log.info('%s: Right Mouse Drop Event: %s %s', type(self), event, trigger)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_drop_event(event, trigger)

    @override
    def on_left_mouse_button_up_event(self: Self, event: events.MouseButtonEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug('%s: Left Mouse Button Up Event: %s', type(self), event)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))

        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_left_mouse_button_up_event(event)

    @override
    def on_middle_mouse_button_up_event(self: Self, event: events.MouseButtonEvent) -> None:
        """Handle middle mouse button up events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug('%s: Middle Mouse Button Up Event: %s', type(self), event)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))

        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_button_up_event(event)

    @override
    def on_right_mouse_button_up_event(self: Self, event: events.MouseButtonEvent) -> None:
        """Handle right mouse button up events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        self.log.info('%s: Right Mouse Button Up Event: %s', type(self), event)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))

        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_button_up_event(event)

    @override
    def on_left_mouse_button_down_event(self: Self, event: events.MouseButtonEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        self.log.debug('=== Scene: Left Mouse Button Down ===')
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))
        self.log.debug('Click position: %s', event_pos)

        # Get sprites at click position
        collided_sprites = self._get_collided_sprites(event_pos)
        self.log.debug('Collided sprites: %s', [type(s).__name__ for s in collided_sprites])
        focusable_sprites = self._get_focusable_sprites(collided_sprites)
        self.log.debug('Focusable sprites: %s', focusable_sprites)

        # Find currently focused sprites
        focused_sprites = self._get_focused_sprites()
        self.log.debug('Currently focused sprites: %s', [type(s).__name__ for s in focused_sprites])

        # Handle focus management
        self._handle_focus_management(collided_sprites)

        # Process the click for collided sprites
        for sprite in collided_sprites:
            if hasattr(sprite, 'on_left_mouse_button_down_event'):
                sprite.on_left_mouse_button_down_event(event)

    @override
    def on_middle_mouse_button_down_event(self: Self, event: events.MouseButtonEvent) -> None:
        """Handle middle mouse button down events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN    pos, button
        self.log.debug('%s: Middle Mouse Button Down Event: %s', type(self), event)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))

        collided_sprites = self.sprites_at_position(pos=event_pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_button_down_event(event)

    @override
    def on_right_mouse_button_down_event(self: Self, event: events.MouseButtonEvent) -> None:
        """Handle right mouse button down events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.info('%s: Right Mouse Button Down Event: %s', type(self), event)
        event_pos: tuple[int, int] = getattr(event, 'pos', (0, 0))

        collided_sprites = self._get_collided_sprites(event_pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_button_down_event(event)

    @override
    def on_sys_wm_event(self: Self, event: events.HashableEvent) -> None:
        """Handle sys wm events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug('%s: Sys WM Event: %s', type(self), event)

    @override
    def on_text_editing_event(self: Self, event: events.TextEditingEvent) -> None:
        """Handle text editing events.

        Args:
            event (TextEditingEvent): The event to handle.

        """
        self.log.debug('%s: Text Editing Event: %s', type(self), event)

    @override
    def on_text_input_event(self: Self, event: events.TextInputEvent) -> None:
        """Handle text input events.

        Args:
            event (TextInputEvent): The event to handle.

        """
        self.log.debug('%s: Text Input Event: %s', type(self), event)

    @override
    def on_touch_down_event(self: Self, event: events.TouchFingerEvent) -> None:
        """Handle touch down events.

        Args:
            event (TouchFingerEvent): The event to handle.

        """
        # TOUCHBUTTONDOWN  touch, pos, button
        self.log.debug('%s: Touch Down Event: %s', type(self), event)

    @override
    def on_touch_motion_event(self: Self, event: events.TouchFingerEvent) -> None:
        """Handle touch motion events.

        Args:
            event (TouchFingerEvent): The event to handle.

        """
        # TOUCHMOTION      touch, pos
        self.log.debug('%s: Touch Motion Event: %s', type(self), event)

    @override
    def on_touch_up_event(self: Self, event: events.TouchFingerEvent) -> None:
        """Handle touch up events.

        Args:
            event (TouchFingerEvent): The event to handle.

        """
        # TOUCHBUTTONUP    touch, pos
        self.log.debug('%s: Touch Up Event: %s', type(self), event)

    @override
    def on_user_event(self: Self, event: events.HashableEvent) -> None:
        """Handle user events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # USEREVENT        code
        self.log.debug('%s: User Event: %s', type(self), event)

    @override
    def on_video_expose_event(self: Self, event: events.HashableEvent) -> None:
        """Handle video expose events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # VIDEOEXPOSE      none
        self.log.debug('%s: Video Expose Event: %s', type(self), event)

    @override
    def on_video_resize_event(self: Self, event: events.VideoResizeEvent) -> None:
        """Handle video resize events.

        Args:
            event (VideoResizeEvent): The event to handle.

        """
        # VIDEORESIZE      size, w, h
        self.log.debug('%s: Video Resize Event: %s', type(self), event)

    @override
    def on_window_close_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window close events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWCLOSE      none
        self.log.debug('%s: Window Close Event: %s', type(self), event)

    @override
    def on_window_enter_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window enter events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWENTER      none
        self.log.debug('%s: Window Enter Event: %s', type(self), event)

    @override
    def on_window_exposed_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window exposed events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWEXPOSED    none
        self.log.debug('%s: Window Exposed Event: %s', type(self), event)

    @override
    def on_window_focus_gained_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window focus gained events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWFOCUSGAINED none
        self.log.debug('%s: Window Focus Gained Event: %s', type(self), event)

    @override
    def on_window_focus_lost_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window focus lost events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWFOCUSLOST  none
        self.log.debug('%s: Window Focus Lost Event: %s', type(self), event)

    @override
    def on_window_hidden_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window hidden events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWHIDDEN     none
        self.log.debug('%s: Window Hidden Event: %s', type(self), event)

    @override
    def on_window_hit_test_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window hit test events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWHITTEST    pos
        self.log.debug('%s: Window Hit Test Event: %s', type(self), event)

    @override
    def on_window_leave_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window leave events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWLEAVE      none
        self.log.debug('%s: Window Leave Event: %s', type(self), event)

    @override
    def on_window_maximized_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window maximized events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWMAXIMIZED  none
        self.log.debug('%s: Window Maximized Event: %s', type(self), event)

    @override
    def on_window_minimized_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window minimized events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWMINIMIZED  none
        self.log.debug('%s: Window Minimized Event: %s', type(self), event)

    @override
    def on_window_moved_event(self: Self, event: events.WindowGeometryEvent) -> None:
        """Handle window moved events.

        Args:
            event (WindowGeometryEvent): The event to handle.

        """
        # WINDOWMOVED      pos
        self.log.debug('%s: Window Moved Event: %s', type(self), event)

    @override
    def on_window_resized_event(self: Self, event: events.WindowGeometryEvent) -> None:
        """Handle window resized events.

        Args:
            event (WindowGeometryEvent): The event to handle.

        """
        # WINDOWRESIZED    size, w, h
        self.log.debug('%s: Window Resized Event: %s', type(self), event)

    @override
    def on_window_restored_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window restored events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWRESTORED   none
        self.log.debug('%s: Window Restored Event: %s', type(self), event)

    @override
    def on_window_shown_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window shown events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWSHOWN      none
        self.log.debug('%s: Window Shown Event: %s', type(self), event)

    @override
    def on_window_size_changed_event(self: Self, event: events.WindowGeometryEvent) -> None:
        """Handle window size changed events.

        Args:
            event (WindowGeometryEvent): The event to handle.

        """
        # WINDOWSIZECHANGED size, w, h
        self.log.debug('%s: Window Size Changed Event: %s', type(self), event)

    @override
    def on_window_take_focus_event(self: Self, event: events.WindowEvent) -> None:
        """Handle window take focus events.

        Args:
            event (WindowEvent): The event to handle.

        """
        # WINDOWTAKEFOCUS  none
        self.log.debug('%s: Window Take Focus Event: %s', type(self), event)

    @override
    def on_quit_event(self: Self, event: events.HashableEvent) -> None:
        """Handle quit events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # QUIT             none
        self.log.debug('%s: %s', type(self), event)

    @override
    def on_fps_event(self: Self, event: events.FpsEvent) -> None:
        """Handle FPS events.

        Args:
            event (FpsEvent): The event to handle.

        """
        # FPSEVENT is pygame.USEREVENT + 1
        # Log FPS at the specified interval to reduce log spam. The frame clock starts at 0, so
        # the first log waits one full interval of play
        current_time = frame_clock_seconds()

        # Use the configured log interval instead of hardcoded 1.0 second
        log_interval_seconds = float(self.scene_manager.fps_log_interval_ms) / 1000.0
        if current_time - self._last_fps_log_time >= log_interval_seconds:
            event_fps: float = getattr(event, 'fps', 0.0)
            self.log.info('Scene "%s" (%s) FPS: %s', self.NAME, type(self), event_fps)
            self._last_fps_log_time = current_time

        self.fps = getattr(event, 'fps', 0.0)

    def load_resources(self: Self) -> None:
        """Load the scene's resources."""
        self.log.debug('Implement load_resource() in %s.', type(self))

    @override
    def on_key_down_event(self, event: events.KeyEvent) -> None:
        """Handle key down events."""
        self.log.debug('%s: On Key Down Event %s', type(self), event)

        # Check if focused sprites handle the event
        if self._handle_focused_sprite_events(event):
            return

        # Only process scene-level key events if no focused sprite handled it
        self._handle_scene_key_events(event)

    def _handle_focused_sprite_events(self, event: events.KeyEvent) -> bool:
        """Handle events for focused sprites.

        Args:
            event: The event to handle

        Returns:
            True if a focused sprite handled the event, False otherwise

        """
        # Find the currently focused sprite
        focused_sprites = [
            sprite
            for sprite in self.all_sprites
            if hasattr(sprite, 'is_active') and sprite.is_active
        ]

        if focused_sprites:
            # If we have focused sprites, only they get the events
            for sprite in focused_sprites:
                if hasattr(sprite, 'on_key_down_event'):
                    sprite.on_key_down_event(event)
                    return True  # Stop event propagation after handling

        return False

    def _handle_scene_key_events(self, event: events.KeyEvent) -> None:
        """Handle scene-level key events.

        Args:
            event: The event to handle

        """
        event_key: int | None = getattr(event, 'key', None)
        if event_key == pygame.K_q:
            self.log.info('Quit requested')
            self.quit_requested = True

    def on_text_submit_event(self, text: str) -> None:
        """Handle text submission from MultiLineTextBox.

        Args:
            text (str): The submitted text.

        """
        self.log.info("Text submitted: '%s'", text)

    @override
    def pause(self: Self) -> None:
        """Pause the current scene.

        Default implementation requests a PauseScene for the end of this frame.
        Scenes can override this method to provide custom pause behavior.

        The switch happens after this frame renders (via next_scene), not immediately: pause()
        usually runs during event processing, after sprites have moved this frame, so an
        immediate switch would freeze the previous frame's picture one frame behind the game.

        """
        from .builtin_scenes.pause_scene import PauseScene

        self.next_scene = PauseScene(options=self.options)

        self.log.info('Scene pause requested')

    def resume(self: Self) -> None:
        """Resume the current scene.

        Default implementation switches back to the previous scene.
        Scenes can override this method to provide custom resume behavior.

        """
        if self.scene_manager.previous_scene:
            self.scene_manager.switch_to_scene(self.scene_manager.previous_scene)
            self.log.info('Scene resumed')
        else:
            self.log.warning('No previous scene found to resume')

    def game_over(self: Self) -> None:
        """Handle game over for the current scene.

        Default implementation switches to a GameOverScene.
        Scenes can override this method to provide custom game over behavior.

        """
        from .builtin_scenes.game_over_scene import GameOverScene

        # Create the game over scene
        game_over_scene = GameOverScene(options=self.options)

        # Switch to the game over scene
        self.scene_manager.switch_to_scene(game_over_scene)

        self.log.info('Game over')
