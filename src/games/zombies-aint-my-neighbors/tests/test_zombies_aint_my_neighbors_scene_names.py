"""Every scene's name, which the window's title shows: the game's name, and the part shown."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys

import pytest

import zombies_aint_my_neighbors
from glitchygames.scenes import Scene
from zombies_aint_my_neighbors.text import GAME_NAME

# The scenes the game shows on its own, by their window title (the owner, 2026-11-19: the intro
# and the demo, and every other part, read "Zombies Ain't My Neighbors - <part>")
EXPECTED_NAMES = {
    'zombies_aint_my_neighbors.title:TitleScene': "Zombies Ain't My Neighbors",
    'zombies_aint_my_neighbors.neighborhood:NeighborhoodScene': "Zombies Ain't My Neighbors",
    'zombies_aint_my_neighbors.game_over:GameOverScene': "Zombies Ain't My Neighbors",
    'zombies_aint_my_neighbors.intro:IntroScene': "Zombies Ain't My Neighbors - Intro",
    'zombies_aint_my_neighbors.attract:AttractScene': "Zombies Ain't My Neighbors - Demo",
    'zombies_aint_my_neighbors.demo_neighborhood:DemoNeighborhoodScene': (
        "Zombies Ain't My Neighbors - Demo"
    ),
    'zombies_aint_my_neighbors.feature_card:FeatureCardScene': (
        "Zombies Ain't My Neighbors - Feature Presentation"
    ),
}


def game_scene_classes() -> dict[str, type[Scene]]:
    """Return every scene class the game's package defines, by ``module:class``.

    Returns:
        Them, the abstract bases (no NAME of their own) included.

    """
    found: dict[str, type[Scene]] = {}
    for module_info in pkgutil.walk_packages(
        zombies_aint_my_neighbors.__path__, prefix='zombies_aint_my_neighbors.'
    ):
        # Never __main__: importing it leaves it in sys.modules, where runpy (the python -m
        # test) trips on it, and it defines no scene
        if module_info.name.rsplit('.', 1)[-1] == '__main__':
            continue
        module = importlib.import_module(module_info.name)
        for name, value in inspect.getmembers(module, inspect.isclass):
            if issubclass(value, Scene) and value.__module__ == module.__name__:
                found[f'{module.__name__}:{name}'] = value
    return found


@pytest.mark.parametrize(('scene', 'expected'), EXPECTED_NAMES.items())
def test_each_scene_is_named_for_the_game_and_its_part(scene: str, expected: str):
    """Each scene's name, as the window's title shows it while that scene plays."""
    assert expected == game_scene_classes()[scene].NAME


def test_every_scene_that_names_itself_names_the_game_first():
    """A scene added later is named the game's name, or the game's name, " - ", its part."""
    named = {
        scene: scene_class.NAME
        for scene, scene_class in game_scene_classes().items()
        if 'NAME' in vars(scene_class)
    }

    assert named == EXPECTED_NAMES
    assert all(name == GAME_NAME or name.startswith(f'{GAME_NAME} - ') for name in named.values())


def test_finding_the_scenes_never_imports_the_packages_main():
    """The walk skips ``__main__``: importing it leaves it in sys.modules for runpy to trip on."""
    sys.modules.pop('zombies_aint_my_neighbors.__main__', None)

    game_scene_classes()

    assert 'zombies_aint_my_neighbors.__main__' not in sys.modules
