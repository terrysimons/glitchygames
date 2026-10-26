"""Brave Adventurer and Papyrus moved from glitchygames/examples into one project.

Their recordings did not change: each scene keeps its logical name and both goldens keep their
history.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

import brave_adventurer.game
import brave_adventurer_papyrus.game
from glitchygames.logical_names import logical_name
from glitchygames.recording_metrics import RECORDING_PATH_RENAMES
from glitchygames.scenes import Scene
from glitchygames.testing.replays import recording_console_script

PROJECT_ROOT = Path(__file__).resolve().parents[4]
MEMBER_DIRECTORY = Path(__file__).resolve().parents[1]
REPLAY_FIXTURES_DIRECTORY = MEMBER_DIRECTORY / 'tests' / 'fixtures' / 'replays'
# Each game's golden replay: where it was in the engine's tests, where it is now, and the
# console script that replays it
GOLDENS = [
    (
        'tests/fixtures/replays/brave-adventurer/golden.jsonl.gz',
        'golden-classic.jsonl.gz',
        'brave-adventurer',
    ),
    (
        'tests/fixtures/replays/brave-adventurer-papyrus/golden.jsonl.gz',
        'golden-papyrus.jsonl.gz',
        'brave-adventurer-papyrus',
    ),
]


def scene_classes(module):
    """Return the scene classes a game module defines (not those it imports).

    Returns:
        The classes.

    """
    return [
        scene_class
        for _name, scene_class in inspect.getmembers(module, inspect.isclass)
        if issubclass(scene_class, Scene) and scene_class.__module__ == module.__name__
    ]


@pytest.mark.parametrize('game_module', [brave_adventurer.game, brave_adventurer_papyrus.game])
def test_both_games_keep_their_logical_names(game_module):
    """Recordings name games.<package>.game:<scene>, as before the move."""
    package = game_module.__name__.partition('.')[0]
    scenes = scene_classes(game_module)

    assert scenes, f'{game_module.__name__} defines its scenes'
    for scene_class in scenes:
        assert logical_name(scene_class=scene_class) == (
            f'games.{package}.game:{scene_class.__qualname__}'
        )


def test_the_scene_classes_kept_their_names():
    """Each scene class stays in its game's game.py under its old name."""
    assert brave_adventurer.game.BraveAdventurerScene.__module__ == 'brave_adventurer.game'
    assert brave_adventurer_papyrus.game.PapyrusBraveAdventurerScene.__module__ == (
        'brave_adventurer_papyrus.game'
    )


@pytest.mark.parametrize(
    'old_package',
    ['glitchygames.examples.brave_adventurer', 'glitchygames.examples.brave_adventurer_papyrus'],
)
def test_the_old_example_packages_are_gone(old_package):
    """Nothing is left in glitchygames/examples to import (a stale __pycache__ would be)."""
    assert importlib.util.find_spec(old_package) is None
    old_directory = PROJECT_ROOT.joinpath('src', *old_package.split('.'))
    assert not old_directory.exists()


@pytest.mark.parametrize(('old_path', 'new_name', 'console_script'), GOLDENS)
def test_both_goldens_keep_their_history(old_path, new_name, console_script):
    """Each golden moved (its ledger rows follow it) and still replays through its own game."""
    new_path = REPLAY_FIXTURES_DIRECTORY / new_name

    assert new_path.is_file()
    assert not (PROJECT_ROOT / old_path).exists()
    assert RECORDING_PATH_RENAMES[old_path] == new_path.relative_to(PROJECT_ROOT).as_posix()
    assert recording_console_script(path=new_path) == console_script
