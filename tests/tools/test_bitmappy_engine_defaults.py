"""Bitmappy's engine defaults.

Split from tests/engine/test_engine_initialization.py; they move with Bitmappy.
"""

import argparse
import math

from glitchygames.bitmappy.editor import BitmapEditorScene
from glitchygames.engine import GameEngine
from glitchygames.engine.game_engine import DEFAULT_TARGET_FPS


def test_bitmappy_gets_engine_default(mocker):
    """Bitmappy declares no TARGET_FPS, so it runs at the engine's default."""
    mocker.patch(
        'argparse.ArgumentParser.parse_args',
        return_value=argparse.Namespace(log_level='INFO', target_fps=None),
    )
    options = GameEngine.initialize_arguments(BitmapEditorScene)
    assert math.isclose(options['target_fps'], DEFAULT_TARGET_FPS, abs_tol=1e-9)
