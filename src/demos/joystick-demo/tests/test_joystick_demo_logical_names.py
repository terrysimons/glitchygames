"""The joystick demo's Game keeps its logical name in the demos layer."""

from __future__ import annotations

from glitchygames.logical_names import logical_name
from joystick_demo import Game


def test_the_demo_is_named_in_the_demos_layer():
    """Game stays defined in the package itself, so its logical name is demos.joystick_demo:Game."""
    assert logical_name(scene_class=Game) == 'demos.joystick_demo:Game'
    assert Game.__module__ == 'joystick_demo'
