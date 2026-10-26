"""PaddleSlap moved out of glitchygames/examples: its logical name and history stayed."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import paddleslap
from glitchygames.logical_names import logical_name
from glitchygames.recording_metrics import RECORDING_PATH_RENAMES
from glitchygames.testing.replays import bundled_demo_paths
from paddleslap import Game

# The rally demo ships inside the package (package data), beside its __init__.py
RALLY_DEMO_PATH = Path(paddleslap.__file__).parent / 'demos' / 'rally.jsonl.gz'
# Where the rally demo is now, and every path it had before, relative to the repository
RALLY_DEMO_REPOSITORY_PATH = 'src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz'
RALLY_DEMO_FORMER_PATHS = (
    'glitchygames/examples/paddleslap_demos/rally.jsonl.gz',
    'src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz',
    'src/games/paddleslap/paddleslap/demos/rally.jsonl.gz',
)
GOLDEN_REPOSITORY_PATH = 'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz'
GOLDEN_FORMER_PATH = 'tests/fixtures/replays/paddleslap/golden.jsonl.gz'


def test_paddleslap_game_keeps_its_logical_name():
    """Game stays defined in the package itself, so its recordings' games.paddleslap:Game holds."""
    assert logical_name(scene_class=Game) == 'games.paddleslap:Game'
    assert Game.__module__ == 'paddleslap'


def test_the_old_example_module_is_gone():
    """Nothing is left in glitchygames/examples to import (a stale __pycache__ would be)."""
    assert importlib.util.find_spec('glitchygames.examples.paddleslap') is None


def test_python_dash_m_paddleslap_runs_the_games_main():
    """The old ``python -m glitchygames.examples.paddleslap`` is ``python -m paddleslap`` now."""
    package_main = importlib.import_module('paddleslap.__main__')

    assert package_main.main is paddleslap.main


def test_bundled_demos_are_found_in_member_packages():
    """The rally demo is found inside the paddleslap package and replayed by its console script."""
    assert ('paddleslap', RALLY_DEMO_PATH) in bundled_demo_paths()
    assert RALLY_DEMO_PATH == paddleslap.PADDLESLAP_DEMO_PATH
    assert RALLY_DEMO_PATH.is_file()


def test_the_rally_demo_keeps_its_whole_history():
    """Each of the demo's former paths maps straight to its new one: a lookup is one step."""
    for former_path in RALLY_DEMO_FORMER_PATHS:
        assert RECORDING_PATH_RENAMES[former_path] == RALLY_DEMO_REPOSITORY_PATH


def test_paddleslaps_golden_keeps_its_history():
    """PaddleSlap's golden moved into its member: its rows from before the move follow."""
    assert RECORDING_PATH_RENAMES[GOLDEN_FORMER_PATH] == GOLDEN_REPOSITORY_PATH


def test_paddleslap_is_imported_from_its_src_directory():
    """PaddleSlap's package is under its member's src/ (or site-packages in a wheel install)."""
    member_source_directory = Path(__file__).resolve().parents[1] / 'src'
    package_directory = Path(paddleslap.__file__).resolve().parent

    assert (
        package_directory.parent == member_source_directory
        or 'site-packages' in package_directory.parts
    ), f'{package_directory} is not under {member_source_directory} or site-packages'
