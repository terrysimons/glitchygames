"""The dt demo's Game keeps its logical name in the demos layer."""

from __future__ import annotations

from dt_demo import Game
from glitchygames.logical_names import logical_name


def test_the_demo_is_named_in_the_demos_layer():
    """Game stays defined in the package itself, so its logical name is demos.dt_demo:Game."""
    assert logical_name(scene_class=Game) == 'demos.dt_demo:Game'
    assert Game.__module__ == 'dt_demo'
