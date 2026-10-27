r"""Record a scripted session of a game through the real engine (``GameEngine.start``).

A scripted session is a game run for real, frame loop and all, with ``--record-trace``, while a
supervisor (glitchygames/supervision.py) plays an input script (``InputScript``,
glitchygames/replay/tools/golden_traces.py): at the supervisor slot of frame N it posts the
script's key events and per-frame input for frame N + 1 with
``glitchygames.recording.post_input_event``, so the recording holds them as external input,
exactly what a player's keys are. ``frame_count`` plays the script's frames 0 to
``frame_count`` - 1. The ``record-session`` tool (glitchygames/replay/tools/registry.py) runs it on
the game it is given, with the input script named ``MODULE:NAME`` (``load_input_script``); our
own games' golden replays are recorded by scripts/record_scripted_session.py.

The controls tail (``controls_tail``): after the script's frames the supervisor plays it. Its
first frame releases every key the script left held; then it presses whatever it holds (a
golden replay's tail exercises the controls the script does not), and it must end with the
game's own quit control. The game ends the run: the recording's last frame holds the QUIT the
game posted (internal), so a replay whose game no longer quits diverges ("missing internal
event"). A game still running ``QUIT_WAIT_FRAMES`` after the tail's last input fails the
recording (``GameDidNotQuitError``). A session is N + T + 2 frames long, T being the tail frame
of its last input (the quit): the game posts QUIT while handling that frame's events, and the
next frame (the last) pumps it. Without a tail, at frame N - 1 the supervisor ends the run
(``SceneManager.quit_requested``, no event), so the recording holds frames 0 to N - 1 and no
quit.

Unlike the golden-trace harness, the session runs the real frame loop (``SceneManager.start``):
frames are paced at the game's target FPS, each frame's ``dt`` is measured and FPS events are
posted, so a ``--replay-trace`` replay of the recording (which runs the same loop) matches it
frame for frame. Recording takes real time (about 60 frames a second), and two recordings of
the same script never have the same bytes (measured frame times differ).

Script placements move sprites directly (they are not input), so a session may not run a frame
a placement is scheduled before, unless the placements only steer the script's own input
(``input_only_placements``: PaddleSlap's release its tracked keys and resume tracking). Input
scheduled before frame 0 cannot be posted (there is no supervisor slot before it) and is
refused.

A game that reads its controls from the frame's polled input (``current_input()``) never sees a
posted event there: SDL updates its polled state only for a real device's events. With
``polled_input`` the session's live snapshots show the supervisor's posted input
(``PostedPolledInput``, ``polled_input_follows``), as a real player's would. Only then: without
it a session records the snapshots it always did (held keys absent), so a game's re-recordings
keep their content hashes.

Host environment events (window shown and focus, audio devices) the dummy video driver posts are
external and are recorded; a replay serves them as recorded, so they are harmless. The session
drops those queued before the first frame (as the golden-trace harness does), because SDL's dummy
driver posts a focus-lost event at startup that would auto-pause a game that pauses on it.

The session never chooses the video driver: whoever runs it does (SDL's dummy drivers in the
tests and scripts/record_scripted_session.py, ``--headless`` on a game). Importing this module
imports the engine (``GameEngine``), so the tool table imports it only when the tool runs.

Moved from scripts/record_scripted_session.py (Stage D, Task D4b), re-keyed from our game keys
to a scene class, an input script and flags (``polled_input``, ``input_only_placements``).
"""

from __future__ import annotations

import contextlib
import dataclasses
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, TypedDict, Unpack

import pygame

from glitchygames import live_sources
from glitchygames.input.state import MOUSE_BUTTON_COUNT
from glitchygames.logical_names import logical_name
from glitchygames.recording import post_input_event
from glitchygames.replay.tools.golden_traces import (
    SCREEN_RESOLUTION,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    InputScript,
    command_line,
    deterministic_environment,
    discard_environment_events,
    release,
    seed_arguments,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from glitchygames.input.state import InputSnapshot
    from glitchygames.scenes import Scene, SceneManager

# The live doors' one polling function (glitchygames/live_sources.py), which a session replaces
# so its snapshots show the posted input (polled_input_follows)
LIVE_CAPTURE_FUNCTION_NAME = 'capture_live_snapshot'

# A controls tail's quit must end the run within this many frames of the tail's last input
QUIT_WAIT_FRAMES = 10


class GameDidNotQuitError(RuntimeError):
    """The game was still running QUIT_WAIT_FRAMES after its controls tail pressed quit."""


class PostedPolledInput:
    """The polled input a real keyboard and mouse would leave behind the supervisor's events.

    SDL updates its polled state (``pygame.key.get_pressed``, ``pygame.mouse.get_pos`` and
    ``get_pressed``) as a real device's events arrive, never for a posted event, so on its own a
    supervisor's key press is an event that no snapshot shows held. A game that reads held keys
    or the mouse from the frame's snapshot (``current_input()``) would never see the script
    play. This follows each posted event (a key held from its KEYDOWN to its KEYUP, by
    scancode; the mouse's position and buttons) and ``overlay`` lays it over a live snapshot,
    so the session's snapshots agree with its events as a real player's do. A replay serves the
    recorded snapshots, so it needs none of this.
    """

    def __init__(self) -> None:
        """Start with nothing posted: no key held, the mouse unmoved, its buttons up."""
        self.held_scancodes: set[int] = set()
        self.mouse_position: tuple[int, int] | None = None
        self.mouse_buttons = [False] * MOUSE_BUTTON_COUNT

    def follow(self, event: pygame.event.Event) -> None:
        """Note what a posted event changes in the polled input.

        Args:
            event: The posted event.

        """
        if event.type == pygame.KEYDOWN:
            self.held_scancodes.add(event.scancode)
        elif event.type == pygame.KEYUP:
            self.held_scancodes.discard(event.scancode)
        elif event.type == pygame.MOUSEMOTION:
            self.mouse_position = event.pos
        elif event.type in {pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP}:
            # pygame numbers the buttons from 1 (left, middle, right); the snapshot from 0
            button_index = event.button - 1
            if button_index < MOUSE_BUTTON_COUNT:
                self.mouse_buttons[button_index] = event.type == pygame.MOUSEBUTTONDOWN

    def overlay(self, snapshot: InputSnapshot) -> InputSnapshot:
        """Lay the posted input over a live snapshot.

        Args:
            snapshot: The live snapshot.

        Returns:
            The snapshot with the posted held keys added, the posted mouse position (once the
            mouse was moved) and the posted mouse buttons.

        """
        return dataclasses.replace(
            snapshot,
            pressed_scancodes=snapshot.pressed_scancodes | frozenset(self.held_scancodes),
            mouse_position=self.mouse_position or snapshot.mouse_position,
            mouse_buttons=tuple(
                live or posted
                for live, posted in zip(snapshot.mouse_buttons, self.mouse_buttons, strict=True)
            ),
        )


@contextlib.contextmanager
def polled_input_follows(posted_input: PostedPolledInput) -> Generator[None]:
    """Make the live doors' snapshots show the posted input (``PostedPolledInput``).

    Replaces ``glitchygames.live_sources.capture_live_snapshot`` (the live doors' one polling
    call) with one that overlays the posted input, then puts it back.

    Args:
        posted_input: The input the supervisor posted.

    Yields:
        None, while the live snapshots show it.

    """
    original_capture = live_sources.capture_live_snapshot

    def capture_with_posted_input(**device_positions: Any) -> InputSnapshot:
        return posted_input.overlay(original_capture(**device_positions))

    # By name, as deterministic_environment replaces the save directory: a type checker will not
    # let a module's function be assigned another
    setattr(live_sources, LIVE_CAPTURE_FUNCTION_NAME, capture_with_posted_input)
    try:
        yield
    finally:
        setattr(live_sources, LIVE_CAPTURE_FUNCTION_NAME, original_capture)


class ScriptedInputSupervisor:
    """Posts an input script into the real event queue, one frame ahead.

    A glitchygames.supervision.Supervisor: at the supervisor slot of frame N it runs the
    placements and posts the per-frame input and key events the script holds for frame N + 1, so
    frame N + 1's pump returns them, as the golden-trace harness posts them just before frame
    N + 1.

    Without a controls tail it ends the run at the slot of the last frame (no event). With one,
    the script stops after ``frame_count`` frames: the tail's first frame releases every key the
    script left held, then the tail's input follows (its frames count from there), and the game
    must end the run itself, with the quit control the tail presses; if it is still running
    QUIT_WAIT_FRAMES after the tail's last input, the supervisor ends the run and sets
    ``game_did_not_quit``.
    """

    def __init__(
        self: Self,
        *,
        script: InputScript,
        frame_count: int,
        scene_manager: SceneManager,
        controls_tail: InputScript | None = None,
        input_only_placements: bool = False,
    ) -> None:
        """Check the script can be recorded as input for this many frames.

        Args:
            script: The game's input script.
            frame_count: How many of the script's frames the session plays (frames 0 to
                frame_count - 1); without a controls tail, the session's length.
            scene_manager: The scene manager whose run ends after the last frame.
            controls_tail: Key events played after the script's frames, ending with the game's
                quit control, or None to end after the script.
            input_only_placements: True when the script's placements only steer its own input
                (they move no sprite), so they may run inside the session.

        Raises:
            ValueError: If a placement falls inside the session and ``input_only_placements``
                is False, if the script holds input for frame 0, or if the controls tail holds
                placements, per-frame input or no input at all.

        """
        placed_frames = sorted(
            frame_number for frame_number in script.placements if frame_number < frame_count
        )
        if placed_frames and not input_only_placements:
            message = (
                f'the script places sprites directly at frame {placed_frames[0]}; it cannot be '
                f'recorded as input past frame {placed_frames[0] - 1} (record at most '
                f'{placed_frames[0]} frames, or, if its placements only steer its own input, '
                'allow them: input_only_placements, --input-only-placements)'
            )
            raise ValueError(message)
        if script.key_events.get(0) or script.placements.get(0):
            message = 'the script has input before frame 0, which no supervisor can post'
            raise ValueError(message)
        if controls_tail is not None and (
            controls_tail.placements
            or controls_tail.per_frame is not None
            or not controls_tail.key_events
        ):
            message = 'a controls tail must hold key events only, and some'
            raise ValueError(message)
        self.script = script
        self.frame_count = frame_count
        self.scene_manager = scene_manager
        self.controls_tail = controls_tail
        # Keys the posted script input left down (released when the controls tail starts)
        self.held_keys: set[int] = set()
        # The polled input the posted events would leave behind (polled_input_follows)
        self.posted_input = PostedPolledInput()
        self.game_did_not_quit = False

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Post the next frame's scripted input; end the run at the last frame.

        Args:
            frame_number: The frame being run.
            scene: The active scene at the supervisor slot.

        """
        next_frame = frame_number + 1
        if self.controls_tail is not None and next_frame >= self.frame_count:
            self._post_controls_tail(tail_frame=next_frame - self.frame_count)
            return
        if frame_number >= self.frame_count - 1:
            # No event: the loop ends after this frame, so the recording holds no quit request
            self.scene_manager.quit_requested = True
            return
        if scene is not None:
            for placement in self.script.placements.get(next_frame, []):
                placement(scene)
            # Per-frame input for frame 0 is never posted: no supervisor slot runs before it
            if self.script.per_frame is not None:
                for event in self.script.per_frame(scene):
                    self._post(event)
        for event in self.script.key_events.get(next_frame, []):
            self._post(event)

    def _post_controls_tail(self: Self, *, tail_frame: int) -> None:
        """Post a frame of the controls tail; end the run if the game has not quit in time.

        Args:
            tail_frame: The frame being posted for, counted from the tail's first frame.

        """
        assert self.controls_tail is not None
        if tail_frame == 0:
            for key in sorted(self.held_keys):
                self._post(release(key))
        if tail_frame > max(self.controls_tail.key_events) + QUIT_WAIT_FRAMES:
            self.game_did_not_quit = True
            self.scene_manager.quit_requested = True
            return
        for event in self.controls_tail.key_events.get(tail_frame, []):
            self._post(event)

    def _post(self: Self, event: pygame.event.Event) -> None:
        """Post an event as external input, noting which keys are held and the polled input.

        Args:
            event: The event.

        """
        if event.type == pygame.KEYDOWN:
            self.held_keys.add(event.key)
        elif event.type == pygame.KEYUP:
            self.held_keys.discard(event.key)
        self.posted_input.follow(event)
        post_input_event(event)


def clear_events_left_queued() -> None:
    """Empty the event queue, if pygame's display (and so its queue) is running.

    A session clears it before it starts and after it ends: it records none of what a caller
    that keeps pygame running (a test) left queued, and hands such a caller an empty queue back.
    """
    if pygame.display.get_init():
        pygame.event.clear()


class ScriptedSessionOptions(TypedDict, total=False):
    """How a scripted session is played, given to ``record_scripted_session`` by keyword.

    Attributes:
        controls_tail: Key events played after the script's frames, ending with the game's own
            quit control, so the session ends when the game quits; None (the default) ends it
            after the script's frames.
        polled_input: True when the game reads its controls from the frame's polled input
            (``current_input()``): the live snapshots then show the posted input
            (``polled_input_follows``), as a real player's would. False by default.
        input_only_placements: True when the script's placements only steer its own input, so
            they may run inside the session (``ScriptedInputSupervisor``). False by default.
        random_seed: The run's master seed (``--random-seed``); None (the default) rolls one,
            as any run does.

    """

    controls_tail: InputScript | None
    polled_input: bool
    input_only_placements: bool
    random_seed: int | None


def record_scripted_session(
    *,
    scene_class: type[Scene],
    script: InputScript,
    frame_count: int,
    path: Path,
    **options: Unpack[ScriptedSessionOptions],
) -> None:
    """Run a game for real with an input script and ``--record-trace``.

    Saves go to a temporary directory. The SceneManager singleton is fresh for the session and
    cleared afterwards. GameEngine._shutdown quits pygame at the end, as a real run does.

    Args:
        scene_class: The game's scene class.
        script: Its input script (a fresh one: a per-frame input holds state across frames).
        frame_count: How many of the script's frames to record.
        path: Where the recording goes (its directory is created).
        **options: How the session is played, by keyword (``ScriptedSessionOptions``).

    Raises:
        GameDidNotQuitError: If the controls tail's quit control did not end the run.

    """
    controls_tail = options.get('controls_tail')
    path.parent.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory(prefix='scripted-session-saves-') as save_directory,
        deterministic_environment(save_root=Path(save_directory)),
    ):
        # A caller that keeps pygame running (a test) may have left events queued: a game's own
        # internal events, which this session's first frame would pump and record as its own
        # (and its replay, never posting them, diverges). The session starts on an empty queue
        clear_events_left_queued()
        manager = GoldenTraceSceneManager.install()
        try:
            with command_line([
                '--windowed',
                '--resolution',
                SCREEN_RESOLUTION,
                '--log-level',
                'warning',
                '--input-mode',
                'joystick',
                *seed_arguments(random_seed=options.get('random_seed')),
                '--record-trace',
                str(path),
            ]):
                engine = GoldenTraceEngine(game=scene_class)
            supervisor = ScriptedInputSupervisor(
                script=script,
                frame_count=frame_count,
                scene_manager=manager,
                controls_tail=controls_tail,
                input_only_placements=options.get('input_only_placements', False),
            )
            # After the engine: GameEngine.__init__ resets the scene manager's supervision
            manager.add_supervisor(supervisor=supervisor)
            discard_environment_events()
            with (
                polled_input_follows(supervisor.posted_input)
                if options.get('polled_input')
                else contextlib.nullcontext()
            ):
                engine.start()
        finally:
            # GameEngine._shutdown normally quits pygame (the queue went with it); a caller that
            # keeps pygame running (a test) gets an empty queue back
            clear_events_left_queued()
            GoldenTraceSceneManager.uninstall()
    if supervisor.game_did_not_quit:
        message = (
            f'{logical_name(scene_class=scene_class)} was still running {QUIT_WAIT_FRAMES} '
            f'frames after its controls tail pressed quit: {path} does not end with the game '
            'quitting'
        )
        raise GameDidNotQuitError(message)
