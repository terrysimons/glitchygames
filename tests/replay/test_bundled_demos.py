"""Every demo bundled in a game's package replays without divergence (spec 5.3).

A bundled demo is an ordinary recording shipped in a workspace member's package, as package data
(``<package>/demos/<name>.jsonl.gz``). The suite collects only ``tests/``, so
the demos are reached through this module: one headless replay per demo
(``bundled_demo_paths``, ``replay_recording_headless``; glitchygames/testing/replays.py), so a
change that makes a demo diverge fails here before it ships. PaddleSlap's own tests play its demo
the way the game plays it, through ``SceneManager.play_recording``
(src/games/paddleslap/tests/test_paddleslap_demo_plays_in_game.py).
"""

from __future__ import annotations

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.testing.replays import bundled_demo_paths, replay_recording_headless
from paddleslap import PADDLESLAP_DEMO_PATH

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
