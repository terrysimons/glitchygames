"""The Sound Board demo's Game has its logical name in the demos layer."""

from __future__ import annotations

from glitchygames.logical_names import logical_name
from sound_board_demo import Game


def test_the_demo_is_named_in_the_demos_layer():
    """Game is defined in the package itself, so its logical name is demos.sound_board_demo:Game."""
    assert logical_name(scene_class=Game) == 'demos.sound_board_demo:Game'
    assert Game.__module__ == 'sound_board_demo'
