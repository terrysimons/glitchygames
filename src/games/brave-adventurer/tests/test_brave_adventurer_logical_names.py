"""Brave Adventurer's and Papyrus's scenes keep the logical names their recordings hold."""

from __future__ import annotations

import inspect

import pytest

import brave_adventurer.game
import brave_adventurer_papyrus.game
from glitchygames.logical_names import logical_name
from glitchygames.scenes import Scene


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
