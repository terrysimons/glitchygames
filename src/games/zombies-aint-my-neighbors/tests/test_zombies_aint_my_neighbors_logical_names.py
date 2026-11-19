"""Recordings name the game's scenes games.zombies_aint_my_neighbors.<module>:<scene>."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

import pytest

import zombies_aint_my_neighbors.feature_card
import zombies_aint_my_neighbors.title
from glitchygames.logical_names import logical_name
from glitchygames.scenes import Scene

if TYPE_CHECKING:
    from types import ModuleType

SCENE_MODULES: tuple[ModuleType, ...] = (
    zombies_aint_my_neighbors.title,
    zombies_aint_my_neighbors.feature_card,
)


def scenes_defined_in(module: ModuleType) -> list[type[Scene]]:
    """Return the Scene subclasses a module defines itself (not ones it imports)."""
    return [
        scene_class
        for _name, scene_class in inspect.getmembers(module, inspect.isclass)
        if issubclass(scene_class, Scene) and scene_class.__module__ == module.__name__
    ]


@pytest.mark.parametrize('module', SCENE_MODULES, ids=lambda module: module.__name__)
def test_every_scene_has_its_layered_logical_name(module: ModuleType):
    """Each scene's logical name carries the games layer and its module path."""
    scenes = scenes_defined_in(module)

    assert scenes, f'{module.__name__} defines its scenes'
    for scene_class in scenes:
        assert logical_name(scene_class=scene_class) == (
            f'games.{module.__name__}:{scene_class.__qualname__}'
        )
