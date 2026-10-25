"""Mr. Muncher moved from glitchygames/examples/mr_muncher: its logical names did not change."""

from __future__ import annotations

import inspect

import mr_muncher.game
from glitchygames.logical_names import logical_name
from glitchygames.scenes import Scene


def test_every_scene_keeps_the_logical_name_its_recordings_hold():
    """Recordings made before the move name games.mr_muncher.game:<scene>, as moved code does."""
    scenes = [
        scene_class
        for _name, scene_class in inspect.getmembers(mr_muncher.game, inspect.isclass)
        if issubclass(scene_class, Scene) and scene_class.__module__ == mr_muncher.game.__name__
    ]

    assert scenes, 'mr_muncher.game defines its scenes'
    for scene_class in scenes:
        assert logical_name(scene_class=scene_class) == (
            f'games.mr_muncher.game:{scene_class.__qualname__}'
        )
