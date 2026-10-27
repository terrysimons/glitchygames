r"""Record a scripted session of a game through the real engine (GameEngine.start).

Used for the golden replay fixtures in the workspace members'
``<member>/tests/fixtures/replays/`` (and later for bundled demos). The game's golden
input script (scripts/record_golden_traces.py: SCRIPT_BUILDERS) is played by a supervisor
(glitchygames/supervision.py): at the supervisor slot of frame N it posts the script's key events
and per-frame input for frame N + 1 with ``glitchygames.recording.post_input_event``, so the
recording holds them as external input, exactly what a player's keys are (each key event at its
key's US QWERTY position: ``glitchygames.testing.keys``). ``--frames N`` plays the script's frames
0 to N - 1.

The controls rule (golden replays): after the script's frames the supervisor plays the game's
controls tail (CONTROLS_TAIL_BUILDERS; session-only, so the golden traces, which replay the same
scripts, never see it). Its first frame releases every key the script left held; then it presses
the controls the script does not (each key of an action bound to several, every pause key, a
pause where the script's frames hold none), and ends with the game's own quit control. The game
ends the run: the recording's last frame holds the QUIT the game posted (internal), so a replay
whose game no longer quits diverges ("missing internal event"). A game still running
QUIT_WAIT_FRAMES after the tail's last input fails the recording (GameDidNotQuitError). A session
is N + T + 2 frames long, T being the tail frame of its last input (the quit): the game posts
QUIT while handling that frame's events, and the next frame (the last) pumps it.
tests/replay/test_golden_replays.py checks that every control the game binds is exercised (or
listed with the reason it cannot be: no gamepad in the session), that the game pauses and
resumes, and that the recording ends on the game's own QUIT.

``--script-only`` (demos, and short test sessions: ``exercise_controls=False``) leaves the tail
out: at frame N - 1 the supervisor ends the run (``SceneManager.quit_requested``, no event), so the
recording holds frames 0 to N - 1 and no quit.

Unlike the golden harness, the session runs the real frame loop (``SceneManager.start``): frames
are paced at the game's target FPS and each frame's ``dt`` is measured, and FPS events are posted,
so a ``--replay-trace`` replay of the recording (which runs the same loop) matches it frame for
frame. The golden harness never calls ``SceneManager._finish_frame``, so its recordings hold no
FPS events; do not use it to make replay fixtures. Recording takes real time (about 60 frames a
second).

Script placements move sprites directly (they are not input), so a session may not run a frame a
placement is scheduled before, except for games whose placements only steer the script's own input
(INPUT_ONLY_PLACEMENT_GAMES: PaddleSlap's placements release its tracked keys and resume tracking).
Clockwork Keep (first placement before frame 330) and both Brave Adventurer editions (first
placement before frame 400) are therefore recorded for fewer frames than their placements. Input
scheduled before frame 0 cannot be posted (there is no supervisor slot before it) and is refused.

Host environment events (window shown and focus, audio devices) the dummy video driver posts are
external and are recorded; a replay serves them as recorded, so they are harmless. The session
drops those queued before the first frame (as the golden harness does), because SDL's dummy driver
posts a focus-lost event at startup that would auto-pause Clockwork Keep.

Regenerating the fixtures: only deliberately, after reviewing why they changed, never just to make
a failing golden replay pass (the same rule as the golden traces in tests/world/golden/). A
failing golden replay means the engine or a game no longer reproduces a recorded session; find out
why first. A re-recorded fixture never matches the one it replaces, in content as well as bytes:
each frame's dt is measured in real time, game logic moves by dt (so sprites differ by a few
pixels), FPS events carry the measured rate, and processing times and the header's recorded_at
differ. So diffing an old fixture with a new one shows mostly noise; what counts is that the new
one replays clean and holds the same scenes and scripted input. (A rebaseline keeps the inputs,
dt included: plans/2026-10-20-recording-content-hash-and-history.md.) Then, one command per game:

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game paddleslap --frames 600
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game clockwork_keep --frames 330
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game brave_adventurer --frames 400
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game brave_adventurer_papyrus --frames 400
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game mr_muncher --frames 1950
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game drawing_fire --frames 1600

With their controls tails the recordings hold 622 (PaddleSlap), 532 (Clockwork Keep), 472 (each
Brave Adventurer edition), 2072 (Mr. Muncher) and 1614 (Drawing Fire) frames. Mr. Muncher's
script runs 1950 frames, not more (its death at about frame 1650 and the next life's READY
included), so its fixture stays under 100 KB. Drawing Fire's cannot: its first frame alone is
about 125 KB compressed (the scene start holds every random stream's state, a Mersenne Twister's
625 numbers for each of its 19 streams, twice: at setup and at the first logic frame), so its
fixture is about 185 KB. Its player's first death came between frames 740 and 920 in trial
recordings (frame 809 in the fixture); a re-recording must still hold his death and takeover,
which tests/replay/test_golden_replays.py checks in the recorded internal events.

Drawing Fire reads its controls from the frame's polled input (``current_input()``), which a
posted event never changes in SDL: for the games in POLLED_INPUT_GAMES (Drawing Fire alone) the
session's live snapshots show the supervisor's posted input (PostedPolledInput,
polled_input_follows), as a real player's would. Only for them: every other game's session
records the snapshots it always did, so its re-recordings keep their content hashes.

Without ``--output`` the recording goes to its game's workspace member,
``<member>/tests/fixtures/replays/golden.jsonl.gz`` (``golden-<game>.jsonl.gz`` for each game
of a member holding several: ``GOLDEN_FIXTURE_NAMES``; ``fixture_path``). Keep each fixture
under 100 KB.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from glitchygames import live_sources
from glitchygames.input.state import MOUSE_BUTTON_COUNT
from glitchygames.recording import post_input_event
from glitchygames.replay.tools.children import recording_console_script
from glitchygames.replay.tools.golden_traces import (
    RANDOM_SEED,
    SCREEN_RESOLUTION,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    InputScript,
    command_line,
    deterministic_environment,
    discard_environment_events,
    press,
    release,
)
from scripts.record_golden_traces import GAME_MODULES, GAME_SCENES, PROJECT_ROOT, SCRIPT_BUILDERS
from scripts.workspace_packages import workspace_members

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from glitchygames.input.state import InputSnapshot
    from glitchygames.scenes import Scene, SceneManager

# Games whose script placements only steer the script's own input (they move no sprite)
INPUT_ONLY_PLACEMENT_GAMES = frozenset({'paddleslap'})
# Games that read their controls from the frame's polled input (current_input()), not from
# events: their sessions' live snapshots show the posted input (polled_input_follows). Only
# these: another game's re-recording keeps the snapshots it had (held keys absent), so its
# content hashes, and the metrics ledger's behaviour changes, stay as they were
POLLED_INPUT_GAMES = frozenset({'drawing_fire'})

# Golden replay fixtures: each game's are directly in its workspace member's replay fixtures
# directory. Game key -> the fixtures directory of the workspace member whose package holds the
# game (src/games/mr-muncher/tests/fixtures/replays); every game is in one since Drawing Fire,
# the last in the engine's examples, moved (the root's tests/fixtures/replays/<console-script>/
# layout, which the replay plugin still collects, holds no game's golden)
REPLAY_FIXTURE_DIRECTORIES: dict[str, Path] = {
    game_key: member.replay_fixtures_directory
    for member in workspace_members(project_root=PROJECT_ROOT)
    for game_key, module in GAME_MODULES.items()
    if module.partition('.')[0] in member.import_packages
}
REPLAY_FIXTURE_SUFFIX = '.jsonl.gz'
DEFAULT_FIXTURE_NAME = 'golden'
# Game key -> its golden's name, for the games of a workspace member that holds several: their
# goldens share the member's fixtures directory, so each is named apart (golden-<game>;
# docs/architecture/game_packages.md, "Several games in one project")
GOLDEN_FIXTURE_NAMES: dict[str, str] = {
    'brave_adventurer': 'golden-classic',
    'brave_adventurer_papyrus': 'golden-papyrus',
}

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
    or the mouse from the frame's snapshot (``current_input()``: Drawing Fire) would never see
    the script play. This follows each posted event (a key held from its KEYDOWN to its KEYUP,
    by scancode; the mouse's position and buttons) and ``overlay`` lays it over a live
    snapshot, so the session's snapshots agree with its events as a real player's do. A
    replay serves the recorded snapshots, so it needs none of this.
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


def _pause_with(tail: InputScript, *, key: int, pause_frame: int, resume_frame: int) -> None:
    """Pause with a key, then resume from the engine's pause screen with SPACE.

    Args:
        tail: The controls tail to add to.
        key: The game's pause key (tapped within one frame, as the golden scripts do).
        pause_frame: The tail frame the pause key is tapped before.
        resume_frame: The tail frame SPACE is pressed before (released two frames later).

    """
    tail.at(pause_frame, press(key), release(key))
    tail.at(resume_frame, press(pygame.K_SPACE))
    tail.at(resume_frame + 2, release(pygame.K_SPACE))


def clockwork_keep_controls() -> InputScript:
    """Clockwork Keep: run right (left shift), jump with SPACE, interact, pause, quit with Q.

    Returns:
        The controls tail (frames count from the tail's first frame).

    """
    tail = InputScript()
    tail.at(10, press(pygame.K_LSHIFT))
    tail.at(12, press(pygame.K_RIGHT))
    tail.at(40, release(pygame.K_RIGHT))
    tail.at(42, release(pygame.K_LSHIFT))
    tail.tap(60, pygame.K_SPACE, held_frames=12)
    # Interact away from an elevator: the press is read, nothing rides
    tail.tap(90, pygame.K_w, held_frames=4)
    _pause_with(tail, key=pygame.K_ESCAPE, pause_frame=110, resume_frame=160)
    tail.at(200, press(pygame.K_q))
    return tail


def brave_adventurer_controls() -> InputScript:
    """Brave Adventurer (both editions): walk left, jump with SPACE, quit with Q.

    The golden script already pauses (ESC) and resumes, inside the recorded frames.

    Returns:
        The controls tail (frames count from the tail's first frame).

    """
    tail = InputScript()
    tail.at(10, press(pygame.K_LEFT))
    tail.tap(20, pygame.K_SPACE, held_frames=12)
    tail.at(50, release(pygame.K_LEFT))
    tail.at(70, press(pygame.K_q))
    return tail


def paddleslap_controls() -> InputScript:
    """PaddleSlap: quit with both of the base scene's quit keys, Q and ESC, released together.

    PaddleSlap binds no quit of its own: the engine's Scene quits on the release of Q or ESC
    (each release posts a QUIT), so the recording holds two internal QUITs and a replay in which
    either key no longer quits diverges.

    Returns:
        The controls tail (frames count from the tail's first frame).

    """
    tail = InputScript()
    tail.at(10, press(pygame.K_q))
    tail.at(12, press(pygame.K_ESCAPE))
    tail.at(20, release(pygame.K_q), release(pygame.K_ESCAPE))
    return tail


def mr_muncher_controls() -> InputScript:
    """Mr. Muncher: steer with WASD (the autopilot uses the arrows), pause with P, quit with Q.

    The golden script already pauses with ESC and resumes. The tail is short: the fixture must
    stay under 100 KB.

    Returns:
        The controls tail (frames count from the tail's first frame).

    """
    tail = InputScript()
    for tap_frame, key in ((5, pygame.K_w), (20, pygame.K_a), (35, pygame.K_s), (50, pygame.K_d)):
        tail.tap(tap_frame, key, held_frames=10)
    _pause_with(tail, key=pygame.K_p, pause_frame=65, resume_frame=95)
    tail.at(120, press(pygame.K_q))
    return tail


def drawing_fire_controls() -> InputScript:
    """Drawing Fire: quit with Q (the base scene quits on its release).

    The golden script already uses every control the game reads, the left mouse button and the
    mouse included. Drawing Fire has no pause (tests/replay/test_golden_replays.py
    GAMES_WITHOUT_A_PAUSE), and Escape is the keyboard's Back, never a quit.

    Returns:
        The controls tail (frames count from the tail's first frame).

    """
    tail = InputScript()
    tail.at(10, press(pygame.K_q))
    tail.at(12, release(pygame.K_q))
    return tail


# Game key -> its controls tail: input a golden replay session plays after the golden script's
# frames (never part of the script, so the golden traces never see it). It exercises the
# controls the script does not, pauses where the script's frames hold no pause, and ends with
# the game's own quit control: the recorded QUIT is posted by the game, so a replay whose game
# no longer quits diverges. tests/replay/test_golden_replays.py checks every bound control is
# exercised.
CONTROLS_TAIL_BUILDERS: dict[str, Callable[[], InputScript]] = {
    'clockwork_keep': clockwork_keep_controls,
    'brave_adventurer': brave_adventurer_controls,
    'brave_adventurer_papyrus': brave_adventurer_controls,
    'paddleslap': paddleslap_controls,
    'mr_muncher': mr_muncher_controls,
    'drawing_fire': drawing_fire_controls,
}


def fixture_path(*, game_key: str, name: str | None = None) -> Path:
    """Return where a game's golden replay fixture is stored.

    Args:
        game_key: Which game (a key of GAME_SCENES).
        name: The fixture's name, without the suffix; by default the game's golden
            (``GOLDEN_FIXTURE_NAMES``, else ``DEFAULT_FIXTURE_NAME``).

    Returns:
        ``<member>/tests/fixtures/replays/<name>.jsonl.gz``: every game is in a workspace member
        (``REPLAY_FIXTURE_DIRECTORIES``).

    Raises:
        KeyError: If no workspace member's package holds the game (its member is missing from
            the workspace, or the game from GAME_MODULES).

    """
    if game_key not in REPLAY_FIXTURE_DIRECTORIES:
        message = f'{game_key!r}: no workspace member holds this game, so it has no fixtures'
        raise KeyError(message)
    if name is None:
        name = GOLDEN_FIXTURE_NAMES.get(game_key, DEFAULT_FIXTURE_NAME)
    return REPLAY_FIXTURE_DIRECTORIES[game_key] / f'{name}{REPLAY_FIXTURE_SUFFIX}'


def game_console_script(*, game_key: str) -> str:
    """Return the installed console script that replays a game's golden replay.

    It is found as the replay pytest plugin finds it, so [project.scripts] is the one list: a
    game is replayed by its workspace member's console script (``recording_console_script``),
    and one console script may start several games (Brave Adventurer's launcher starts Classic
    and Papyrus, choosing by the recording's header).

    Args:
        game_key: Which game (a key of GAME_SCENES).

    Returns:
        The console script.

    """
    return recording_console_script(path=fixture_path(game_key=game_key))


# Game key -> the console script (a pyproject.toml's [project.scripts]) that replays its golden
# replay (game_console_script). Keyed by game, not by console script: Classic and Papyrus share
# the member's one script, brave-adventurer
GAME_CONSOLE_SCRIPTS: dict[str, str] = {
    game_key: game_console_script(game_key=game_key) for game_key in SCRIPT_BUILDERS
}


class ScriptedInputSupervisor:
    """Posts a golden input script into the real event queue, one frame ahead.

    A glitchygames.supervision.Supervisor: at the supervisor slot of frame N it runs the
    placements and posts the per-frame input and key events the script holds for frame N + 1, so
    frame N + 1's pump returns them, as the golden harness posts them just before frame N + 1.

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
        game_key: str,
        frame_count: int,
        scene_manager: SceneManager,
        controls_tail: InputScript | None = None,
    ) -> None:
        """Check the script can be recorded as input for this many frames.

        Args:
            script: The game's golden input script.
            game_key: Which game (a key of GAME_SCENES).
            frame_count: How many of the script's frames the session plays (frames 0 to
                frame_count - 1); without a controls tail, the session's length.
            scene_manager: The scene manager whose run ends after the last frame.
            controls_tail: Key events played after the script's frames, ending with the game's
                quit control (CONTROLS_TAIL_BUILDERS), or None to end after the script.

        Raises:
            ValueError: If a placement falls inside the session and the game is not in
                INPUT_ONLY_PLACEMENT_GAMES, if the script holds input for frame 0, or if the
                controls tail holds placements, per-frame input or no input at all.

        """
        placed_frames = sorted(
            frame_number for frame_number in script.placements if frame_number < frame_count
        )
        if placed_frames and game_key not in INPUT_ONLY_PLACEMENT_GAMES:
            message = (
                f'{game_key} script places sprites directly at frame {placed_frames[0]}; it '
                f'cannot be recorded as input past frame {placed_frames[0] - 1} (record at most '
                f'{placed_frames[0]} frames; games allowed to: '
                f'{sorted(INPUT_ONLY_PLACEMENT_GAMES)})'
            )
            raise ValueError(message)
        if script.key_events.get(0) or script.placements.get(0):
            message = f'{game_key} script has input before frame 0, which no supervisor can post'
            raise ValueError(message)
        if controls_tail is not None and (
            controls_tail.placements
            or controls_tail.per_frame is not None
            or not controls_tail.key_events
        ):
            message = f'{game_key} controls tail must hold key events only, and some'
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


def record_scripted_session(
    *,
    game_key: str,
    frame_count: int,
    path: Path,
    exercise_controls: bool,
    random_seed: int = RANDOM_SEED,
) -> None:
    """Run a game for real with its golden input script and ``--record-trace``.

    Saves go to a temporary directory. The SceneManager singleton is fresh for the session and
    cleared afterwards. GameEngine._shutdown quits pygame at the end, as a real run does. For a
    game in POLLED_INPUT_GAMES the live snapshots show the posted input (polled_input_follows),
    as a real player's would.

    Args:
        game_key: Which game (a key of GAME_SCENES).
        frame_count: How many of the script's frames to record.
        path: Where the recording goes (its directory is created).
        exercise_controls: Play the game's controls tail (CONTROLS_TAIL_BUILDERS) after the
            script, so the session ends when the game quits (golden replays); False ends it
            after the script's frames (demos, short test sessions).
        random_seed: The run's master seed (``--random-seed``).

    Raises:
        GameDidNotQuitError: If the controls tail's quit control did not end the run.

    """
    script = SCRIPT_BUILDERS[game_key]()
    controls_tail = CONTROLS_TAIL_BUILDERS[game_key]() if exercise_controls else None
    path.parent.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory(prefix='scripted-session-saves-') as save_directory,
        deterministic_environment(save_root=Path(save_directory)),
    ):
        # A caller that keeps pygame running (a test) may have left events queued: a game's own
        # internal events, which this session's first frame would pump and record as its own
        # (and its replay, never posting them, diverges). The session starts on an empty queue
        if pygame.display.get_init():
            pygame.event.clear()
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
                '--random-seed',
                str(random_seed),
                '--record-trace',
                str(path),
            ]):
                engine = GoldenTraceEngine(game=GAME_SCENES[game_key])
            supervisor = ScriptedInputSupervisor(
                script=script,
                game_key=game_key,
                frame_count=frame_count,
                scene_manager=manager,
                controls_tail=controls_tail,
            )
            # After the engine: GameEngine.__init__ resets the scene manager's supervision
            manager.add_supervisor(supervisor=supervisor)
            discard_environment_events()
            with (
                polled_input_follows(supervisor.posted_input)
                if game_key in POLLED_INPUT_GAMES
                else contextlib.nullcontext()
            ):
                engine.start()
        finally:
            # GameEngine._shutdown normally quits pygame (the queue went with it); a caller that
            # keeps pygame running (a test) gets an empty queue back
            if pygame.display.get_init():
                pygame.event.clear()
            GoldenTraceSceneManager.uninstall()
    if supervisor.game_did_not_quit:
        message = (
            f'{game_key} was still running {QUIT_WAIT_FRAMES} frames after its controls tail '
            f'pressed quit: {path} does not end with the game quitting'
        )
        raise GameDidNotQuitError(message)


def main() -> None:
    """Command line: --game KEY --frames N [--script-only] [--output PATH]."""
    parser = argparse.ArgumentParser(description='Record a scripted session through the engine')
    parser.add_argument('--game', required=True, choices=sorted(GAME_SCENES))
    parser.add_argument(
        '--frames',
        required=True,
        type=int,
        help="how many of the golden script's frames to record",
    )
    parser.add_argument(
        '--script-only',
        action='store_true',
        help="end after the script's frames, without the controls tail and its quit (demos)",
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help="where the recording goes (default: the game's golden replay fixture)",
    )
    arguments = parser.parse_args()
    path = arguments.output or fixture_path(game_key=arguments.game)
    record_scripted_session(
        game_key=arguments.game,
        frame_count=arguments.frames,
        path=path,
        exercise_controls=not arguments.script_only,
    )
    sys.stdout.write(f'{arguments.game}: {arguments.frames} script frames -> {path}\n')


if __name__ == '__main__':
    main()
