"""Every demo bundled in a game's package replays without divergence (spec 5.3).

A bundled demo is an ordinary recording shipped in a workspace member's package, as package data
(``<package>/demos/<name>.jsonl.gz``). The suite collects only ``tests/``, so
the demos are reached through this module: one headless replay per demo
(``bundled_demo_paths``, glitchygames/testing/replays.py; ``replay_recording_headless``,
glitchygames/replay/tools/children.py), so a change that makes a demo diverge fails here before
it ships. PaddleSlap's own tests play its demo the way the game plays it, through
``SceneManager.play_recording``
(src/games/paddleslap/tests/test_paddleslap_demo_plays_in_game.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.workspace_packages import workspace_members

from glitchygames.bundled_demos import bundled_demos
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.children import replay_recording_headless
from glitchygames.testing.replays import bundled_demo_paths
from tests.workspace_expectations import EXPECTED_BUNDLED_DEMOS

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLED_DEMOS = bundled_demo_paths()


def test_paddleslap_ships_a_demo():
    """The bundled demos are the expected ones, each replayed by its own member's console script.

    Compared by ``(package, name)``, not by path: nox's test sessions install the members
    non-editable. This is the replay test's expected set (an empty parametrization would skip,
    not fail), so the demos it replays are exactly these.
    """
    demos = bundled_demos()
    members = workspace_members(project_root=PROJECT_ROOT)

    assert {(demo.package, demo.path.name) for demo in demos} == EXPECTED_BUNDLED_DEMOS
    assert [(console_script, path.name) for console_script, path in BUNDLED_DEMOS] == [
        (demo.console_script, demo.path.name) for demo in demos
    ]
    for demo in demos:
        (member,) = [member for member in members if demo.package in member.import_packages]
        assert demo.console_script in member.console_scripts


@pytest.mark.parametrize(
    ('console_script', 'demo_path'),
    BUNDLED_DEMOS,
    ids=[f'{console_script}/{path.name}' for console_script, path in BUNDLED_DEMOS],
)
def test_bundled_demo_replays_without_divergence(console_script, demo_path):
    """The game still reproduces the demo frame for frame (a headless replay exits SUCCESS)."""
    completed = replay_recording_headless(console_script=console_script, path=demo_path)

    assert completed.returncode == ExitCode.SUCCESS, completed.stdout
