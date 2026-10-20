r"""Record a scripted session of a game through the real engine (GameEngine.start).

Used for the golden replay fixtures under ``tests/fixtures/replays/`` (and later for bundled
demos). The game's golden input script (scripts/record_golden_traces.py: SCRIPT_BUILDERS) is
played by a supervisor (glitchygames/supervision.py): at the supervisor slot of frame N it posts
the script's key events and per-frame input for frame N + 1 with ``pygame.event.post``, so the
next pump returns them as external events, exactly what a player's keys are, and at frame
``frame_count - 1`` it ends the run (``SceneManager.quit_requested``, no event), so the recording
holds frames 0 to ``frame_count - 1``.

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
why first. Then, one command per game:

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python scripts/record_scripted_session.py \
        --game paddleslap --frames 600
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python scripts/record_scripted_session.py \
        --game clockwork_keep --frames 330
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python scripts/record_scripted_session.py \
        --game brave_adventurer --frames 400
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python scripts/record_scripted_session.py \
        --game brave_adventurer_papyrus --frames 400

Without ``--output`` the recording goes to
``tests/fixtures/replays/<console-script>/golden.jsonl.gz`` (``fixture_path``).
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

from scripts.record_golden_traces import (
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
)

if TYPE_CHECKING:
    from glitchygames.scenes import Scene, SceneManager

# Games whose script placements only steer the script's own input (they move no sprite)
INPUT_ONLY_PLACEMENT_GAMES = frozenset({'paddleslap'})

# Golden replay fixtures: tests/fixtures/replays/<console-script>/<name>.jsonl.gz
REPLAY_FIXTURE_DIRECTORY = PROJECT_ROOT / 'tests' / 'fixtures' / 'replays'
REPLAY_FIXTURE_SUFFIX = '.jsonl.gz'
DEFAULT_FIXTURE_NAME = 'golden'

# Console script (pyproject.toml [project.scripts], the fixture's directory name) -> game key
CONSOLE_SCRIPT_GAME_KEYS: dict[str, str] = {
    'clockwork-keep': 'clockwork_keep',
    'brave-adventurer': 'brave_adventurer',
    'brave-adventurer-papyrus': 'brave_adventurer_papyrus',
    'paddleslap': 'paddleslap',
}


def fixture_path(*, game_key: str, name: str = DEFAULT_FIXTURE_NAME) -> Path:
    """Return where a game's golden replay fixture is stored.

    Args:
        game_key: Which game (a key of GAME_SCENES).
        name: The fixture's name, without the suffix.

    Returns:
        ``tests/fixtures/replays/<console-script>/<name>.jsonl.gz``.

    """
    (console_script,) = (
        script for script, key in CONSOLE_SCRIPT_GAME_KEYS.items() if key == game_key
    )
    return REPLAY_FIXTURE_DIRECTORY / console_script / f'{name}{REPLAY_FIXTURE_SUFFIX}'


class ScriptedInputSupervisor:
    """Posts a golden input script into the real event queue, one frame ahead.

    A glitchygames.supervision.Supervisor: at the supervisor slot of frame N it runs the
    placements and posts the per-frame input and key events the script holds for frame N + 1, so
    frame N + 1's pump returns them, as the golden harness posts them just before frame N + 1.
    At the slot of the last frame it ends the run.
    """

    def __init__(
        self: Self,
        *,
        script: InputScript,
        game_key: str,
        frame_count: int,
        scene_manager: SceneManager,
    ) -> None:
        """Check the script can be recorded as input for this many frames.

        Args:
            script: The game's golden input script.
            game_key: Which game (a key of GAME_SCENES).
            frame_count: How many frames the session runs (frames 0 to frame_count - 1).
            scene_manager: The scene manager whose run ends after the last frame.

        Raises:
            ValueError: If a placement falls inside the session and the game is not in
                INPUT_ONLY_PLACEMENT_GAMES, or if the script holds input for frame 0.

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
        self.script = script
        self.frame_count = frame_count
        self.scene_manager = scene_manager

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Post the next frame's scripted input; end the run at the last frame.

        Args:
            frame_number: The frame being run.
            scene: The active scene at the supervisor slot.

        """
        if frame_number >= self.frame_count - 1:
            # No event: the loop ends after this frame, so the recording holds no quit request
            self.scene_manager.quit_requested = True
            return
        next_frame = frame_number + 1
        if scene is not None:
            for placement in self.script.placements.get(next_frame, []):
                placement(scene)
            # Per-frame input for frame 0 is never posted: no supervisor slot runs before it
            if self.script.per_frame is not None:
                for event in self.script.per_frame(scene):
                    pygame.event.post(event)
        for event in self.script.key_events.get(next_frame, []):
            pygame.event.post(event)


def record_scripted_session(
    *, game_key: str, frame_count: int, path: Path, random_seed: int = RANDOM_SEED
) -> None:
    """Run a game for real with its golden input script and ``--record-trace``.

    Saves go to a temporary directory. The SceneManager singleton is fresh for the session and
    cleared afterwards. GameEngine._shutdown quits pygame at the end, as a real run does.

    Args:
        game_key: Which game (a key of GAME_SCENES).
        frame_count: How many frames to record.
        path: Where the recording goes (its directory is created).
        random_seed: The run's master seed (``--random-seed``).

    """
    script = SCRIPT_BUILDERS[game_key]()
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
            # After the engine: GameEngine.__init__ resets the scene manager's supervision
            manager.add_supervisor(
                supervisor=ScriptedInputSupervisor(
                    script=script,
                    game_key=game_key,
                    frame_count=frame_count,
                    scene_manager=manager,
                )
            )
            discard_environment_events()
            engine.start()
        finally:
            # GameEngine._shutdown normally quits pygame (the queue went with it); a caller that
            # keeps pygame running (a test) gets an empty queue back
            if pygame.display.get_init():
                pygame.event.clear()
            GoldenTraceSceneManager.uninstall()


def main() -> None:
    """Command line: --game KEY --frames N [--output PATH]."""
    parser = argparse.ArgumentParser(description='Record a scripted session through the engine')
    parser.add_argument('--game', required=True, choices=sorted(GAME_SCENES))
    parser.add_argument('--frames', required=True, type=int)
    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help="where the recording goes (default: the game's golden replay fixture)",
    )
    arguments = parser.parse_args()
    path = arguments.output or fixture_path(game_key=arguments.game)
    record_scripted_session(game_key=arguments.game, frame_count=arguments.frames, path=path)
    sys.stdout.write(f'{arguments.game}: {arguments.frames} frames -> {path}\n')


if __name__ == '__main__':
    main()
