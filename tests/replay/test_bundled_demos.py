"""Every demo bundled in a game's package replays without divergence (spec 5.3).

A bundled demo is an ordinary recording shipped in the game's package
(``glitchygames/examples/<game>_demos/<name>.jsonl.gz``). The suite collects only ``tests/``, so
the demos are reached through this module: one headless replay per demo
(``bundled_demo_paths``, ``replay_recording_headless``; glitchygames/testing/replays.py), so a
change that makes a demo diverge fails here before it ships. PaddleSlap's demo is also played the
way the game plays it, through ``SceneManager.play_recording``.
"""

from __future__ import annotations

import pytest
from scripts.record_golden_traces import FRAME_SECONDS

# Loaded on purpose: its scene is also named Game, so the playback below must tell PaddleSlap's
# apart by module (glitchygames/replay/playback.py, find_scene_class)
from glitchygames.examples import joystick_demo
from glitchygames.examples.paddleslap import PADDLESLAP_DEMO_PATH, Game
from glitchygames.exit_codes import ExitCode
from glitchygames.live_sources import LiveSources
from glitchygames.testing.replays import bundled_demo_paths, replay_recording_headless
from glitchygames.tracing import FRAMES_FIELD, read_trace_result
from tests.replay.playback_fixtures import step_finishing
from tests.world.test_frame_integration import running_scene

BUNDLED_DEMOS = bundled_demo_paths()


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


def test_the_paddleslap_demo_plays_in_game(mocker):
    """The demo plays to its end inside a running PaddleSlap and returns to the live scene.

    Frames run with ``_finish_frame`` (``step_finishing``), where a playback's frames take the
    recording's dt; the golden harness's ``step`` never feeds a playback the recording's dt.
    The live frames get a fixed dt: measured, one slow frame (a busy machine, a real window's
    first frames) moved the live ball far enough to end the game before the assertions.
    """
    mocker.patch.object(LiveSources, 'frame_seconds', return_value=FRAME_SECONDS)
    assert joystick_demo.Game.__name__ == Game.__name__
    recorded_frames = read_trace_result(path=PADDLESLAP_DEMO_PATH).trace[FRAMES_FIELD]
    with running_scene(Game) as manager:
        live_scene = manager.active_scene
        assert live_scene is not None
        manager.play_recording(path=PADDLESLAP_DEMO_PATH, then=live_scene)

        # The frame that asks runs live; the demo's frames follow
        step_finishing(manager, frames=len(recorded_frames) + 1)

        assert manager.playback_session is None
        assert manager.active_scene is live_scene
        outcome = manager.last_playback_outcome
        assert outcome is not None
        assert outcome.reason == 'end_of_recording'
        assert outcome.frames_played == len(recorded_frames)
