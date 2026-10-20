"""Every demo bundled in a game's package replays without divergence (spec 5.3).

A bundled demo is an ordinary recording shipped in the game's package
(``glitchygames/examples/<game>_demos/<name>.jsonl.gz``). The suite collects only ``tests/``, so
the demos are reached through this module: one headless replay per demo
(``bundled_demo_paths``, ``replay_recording_headless``; glitchygames/testing/replays.py), so a
change that makes a demo diverge fails here before it ships. PaddleSlap's demo is also played the
way the game plays it, through ``SceneManager.play_recording``.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Self

import pytest
from scripts.record_golden_traces import (
    SCREEN_RESOLUTION,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
    deterministic_environment,
    discard_environment_events,
)

from glitchygames.examples.paddleslap import PADDLESLAP_DEMO_PATH, Game
from glitchygames.exit_codes import ExitCode
from glitchygames.process import run_command
from glitchygames.replay.playback import PlaybackOutcome
from glitchygames.testing.replays import (
    REPLAY_TIMEOUT_SECONDS,
    bundled_demo_paths,
    replay_recording_headless,
)
from glitchygames.tracing import FRAMES_FIELD, read_trace_result

if TYPE_CHECKING:
    from glitchygames.scenes import Scene, SceneManager

BUNDLED_DEMOS = bundled_demo_paths()

# Plays PaddleSlap's demo in a fresh interpreter and prints how the playback ended (JSON) on a
# line of its own after OUTCOME_LINE_PREFIX (the engine logs to the same output, also at exit)
OUTCOME_LINE_PREFIX = 'playback outcome: '
PLAY_PADDLESLAP_DEMO_IN_GAME = f"""
from tests.replay.test_bundled_demos import play_paddleslap_demo_in_game
print({OUTCOME_LINE_PREFIX!r} + play_paddleslap_demo_in_game().model_dump_json())
"""


class DemoRequestingSupervisor:
    """Asks for PaddleSlap's demo at frame 0 and ends the run once the demo has ended.

    A glitchygames.supervision.Supervisor. The run also ends after ``frame_limit`` frames, so a
    demo that never ends cannot hang the test.
    """

    def __init__(self: Self, *, scene_manager: SceneManager, frame_limit: int) -> None:
        """Remember the scene manager and the run's frame limit.

        Args:
            scene_manager: The running scene manager.
            frame_limit: The last frame the run may reach.

        """
        self.scene_manager = scene_manager
        self.frame_limit = frame_limit
        # The scene that asked for the demo, and the active scene once the demo had ended
        self.live_scene: Scene | None = None
        self.scene_after_demo: Scene | None = None

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Ask for the demo at frame 0; end the run once the demo has ended, or at the limit.

        Args:
            frame_number: The frame being run.
            scene: The active scene at the supervisor slot.

        """
        if frame_number == 0:
            assert scene is not None
            self.live_scene = scene
            self.scene_manager.play_recording(path=PADDLESLAP_DEMO_PATH, then=scene)
        elif self.scene_manager.last_playback_outcome is not None:
            self.scene_after_demo = scene
            self.scene_manager.quit_requested = True
        elif frame_number >= self.frame_limit:
            self.scene_manager.quit_requested = True


def play_paddleslap_demo_in_game() -> PlaybackOutcome:
    """Play PaddleSlap's bundled demo through ``play_recording`` in PaddleSlap's real frame loop.

    The real loop (``SceneManager.start``, unpaced with ``--target-fps 0``), not the golden
    harness's frame step: a playback's frames take the recording's dt in
    ``SceneManager._finish_frame``, which the harness never calls. Runs in a child interpreter
    (test_the_paddleslap_demo_plays_in_game): a playback finds its scene class by name
    (glitchygames/replay/playback.py, ``find_scene_class``), and this suite loads other scenes
    named ``Game`` (the joystick demo's), which would make the name ambiguous.

    Returns:
        How the playback ended (``SceneManager.last_playback_outcome``), checked to have
        returned to the scene that asked for it.

    """
    recorded_frames = read_trace_result(path=PADDLESLAP_DEMO_PATH).trace[FRAMES_FIELD]
    with (
        tempfile.TemporaryDirectory(prefix='bundled-demo-saves-') as save_directory,
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
                '--target-fps',
                '0',
            ]):
                engine = GoldenTraceEngine(game=Game)
            supervisor = DemoRequestingSupervisor(
                scene_manager=manager, frame_limit=len(recorded_frames) * 2
            )
            # After the engine: GameEngine.__init__ resets the scene manager's supervision
            manager.add_supervisor(supervisor=supervisor)
            discard_environment_events()
            engine.start()
            outcome = manager.last_playback_outcome
        finally:
            GoldenTraceSceneManager.uninstall()
    assert outcome is not None, 'the demo never ended'
    assert supervisor.live_scene is not None
    assert supervisor.scene_after_demo is supervisor.live_scene, 'not back to the live scene'
    return outcome


def test_paddleslap_ships_a_demo():
    """PaddleSlap's demo is found among the bundled demos (the folder is collected)."""
    assert ('paddleslap', PADDLESLAP_DEMO_PATH) in BUNDLED_DEMOS


@pytest.mark.parametrize(
    ('console_script', 'demo_path'),
    BUNDLED_DEMOS,
    ids=[f'{console_script}/{path.name}' for console_script, path in BUNDLED_DEMOS],
)
def test_bundled_demo_replays_without_divergence(console_script, demo_path):
    """The game still reproduces the demo frame for frame (a headless replay exits SUCCESS)."""
    completed = replay_recording_headless(console_script=console_script, path=demo_path)

    assert completed.returncode == ExitCode.SUCCESS, completed.stdout


def test_the_paddleslap_demo_plays_in_game():
    """The demo plays to its end inside a running PaddleSlap and returns to the live scene."""
    recorded_frames = read_trace_result(path=PADDLESLAP_DEMO_PATH).trace[FRAMES_FIELD]

    completed = run_command(
        command=[sys.executable, '-c', PLAY_PADDLESLAP_DEMO_IN_GAME],
        environment=dict(os.environ),
        timeout_seconds=REPLAY_TIMEOUT_SECONDS,
        capture_output=True,
    )

    assert completed.returncode == ExitCode.SUCCESS, completed.stdout
    (outcome_line,) = (
        line for line in completed.stdout.splitlines() if line.startswith(OUTCOME_LINE_PREFIX)
    )
    outcome = PlaybackOutcome.model_validate_json(outcome_line.removeprefix(OUTCOME_LINE_PREFIX))
    assert outcome.reason == 'end_of_recording', completed.stdout
    assert outcome.frames_played == len(recorded_frames)
