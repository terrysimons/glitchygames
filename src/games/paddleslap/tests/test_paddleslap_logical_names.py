"""PaddleSlap's Game keeps the logical name its recordings hold."""

from __future__ import annotations

from glitchygames.logical_names import logical_name
from paddleslap import Game


def test_paddleslap_game_keeps_its_logical_name():
    """Game stays defined in the package itself, so its recordings' games.paddleslap:Game holds."""
    assert logical_name(scene_class=Game) == 'games.paddleslap:Game'
    assert Game.__module__ == 'paddleslap'
