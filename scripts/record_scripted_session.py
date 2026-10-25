r"""Record a scripted session of a game through the real engine (GameEngine.start).

Used for the golden replay fixtures under ``tests/fixtures/replays/`` and the workspace
members' ``<member>/tests/fixtures/replays/`` (and later for bundled demos). The game's golden
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

With their controls tails the recordings hold 622 (PaddleSlap), 532 (Clockwork Keep), 472 (each
Brave Adventurer edition) and 2072 (Mr. Muncher) frames. Mr. Muncher's script runs 1950 frames,
not more (its death at about frame 1650 and the next life's READY included), so its fixture
stays under 100 KB.

Without ``--output`` the recording goes to
``tests/fixtures/replays/<console-script>/golden.jsonl.gz``, or for a game in a workspace member
to ``<member>/tests/fixtures/replays/golden.jsonl.gz`` (``fixture_path``).
Keep each fixture under 100 KB.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Self

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from glitchygames.recording import post_input_event
from glitchygames.testing.replays import console_script_in_module
from scripts.record_golden_traces import (
    GAME_MODULES,
    GAME_SCENES,
    PROJECT_ROOT,
    RANDOM_SEED,
    SCREEN_RESOLUTION,
    SCRIPT_BUILDERS,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    InputScript,
    command_line,
    deterministic_environment,
    discard_environment_events,
    press,
    release,
)
from scripts.workspace_packages import workspace_members

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.scenes import Scene, SceneManager

# Games whose script placements only steer the script's own input (they move no sprite)
INPUT_ONLY_PLACEMENT_GAMES = frozenset({'paddleslap'})

# Golden replay fixtures: tests/fixtures/replays/<console-script>/<name>.jsonl.gz, except a
# workspace member's, directly in its own replay fixtures directory (REPLAY_FIXTURE_DIRECTORIES)
REPLAY_FIXTURE_DIRECTORY = PROJECT_ROOT / 'tests' / 'fixtures' / 'replays'
# Game key -> the fixtures directory of the workspace member whose package holds the game
# (src/games/mr-muncher/tests/fixtures/replays); a game key not in it uses the root layout
REPLAY_FIXTURE_DIRECTORIES: dict[str, Path] = {
    game_key: member.replay_fixtures_directory
    for member in workspace_members(project_root=PROJECT_ROOT)
    for game_key, module in GAME_MODULES.items()
    if module.partition('.')[0] in member.import_packages
}
REPLAY_FIXTURE_SUFFIX = '.jsonl.gz'
DEFAULT_FIXTURE_NAME = 'golden'

# A controls tail's quit must end the run within this many frames of the tail's last input
QUIT_WAIT_FRAMES = 10


class GameDidNotQuitError(RuntimeError):
    """The game was still running QUIT_WAIT_FRAMES after its controls tail pressed quit."""


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
}

# Console script (a pyproject.toml's [project.scripts]) -> game key: the installed console
# script whose entry point is in the game's module (GAME_MODULES), found as the replay pytest
# plugin finds it, so [project.scripts] is the one list
CONSOLE_SCRIPT_GAME_KEYS: dict[str, str] = {
    console_script: game_key
    for game_key in SCRIPT_BUILDERS
    if (console_script := console_script_in_module(module=GAME_MODULES[game_key])) is not None
}


def fixture_path(*, game_key: str, name: str = DEFAULT_FIXTURE_NAME) -> Path:
    """Return where a game's golden replay fixture is stored.

    Args:
        game_key: Which game (a key of GAME_SCENES).
        name: The fixture's name, without the suffix.

    Returns:
        ``<member>/tests/fixtures/replays/<name>.jsonl.gz`` for a game in a workspace member
        (``REPLAY_FIXTURE_DIRECTORIES``), else
        ``tests/fixtures/replays/<console-script>/<name>.jsonl.gz``.

    """
    if game_key in REPLAY_FIXTURE_DIRECTORIES:
        return REPLAY_FIXTURE_DIRECTORIES[game_key] / f'{name}{REPLAY_FIXTURE_SUFFIX}'
    (console_script,) = (
        script for script, key in CONSOLE_SCRIPT_GAME_KEYS.items() if key == game_key
    )
    return REPLAY_FIXTURE_DIRECTORY / console_script / f'{name}{REPLAY_FIXTURE_SUFFIX}'


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
        """Post an event as external input, noting which keys are held.

        Args:
            event: The event.

        """
        if event.type == pygame.KEYDOWN:
            self.held_keys.add(event.key)
        elif event.type == pygame.KEYUP:
            self.held_keys.discard(event.key)
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
    cleared afterwards. GameEngine._shutdown quits pygame at the end, as a real run does.

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
