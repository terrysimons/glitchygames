"""Drawing Fire's scene keeps the logical name its recordings hold."""

from __future__ import annotations

from drawing_fire.game import DrawingFireScene
from glitchygames.logical_names import logical_name


def test_drawing_fire_keeps_its_logical_names():
    """Its scene keeps the logical name its recordings hold, from its new package."""
    assert logical_name(scene_class=DrawingFireScene) == 'games.drawing_fire.game:DrawingFireScene'
    assert DrawingFireScene.__module__ == 'drawing_fire.game'
