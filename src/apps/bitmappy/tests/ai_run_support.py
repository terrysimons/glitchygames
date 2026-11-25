"""Real engines for the tests of Bitmappy's AI: what a run's own command line makes of it.

Each is a windowed run unless its arguments say otherwise, on the test suite's dummy driver. The AI
never reads the driver (``bitmappy.ai_manager.ai_off_reason``), so such a run counts as live. The
engine is ``GoldenTraceEngine``, the real one opening a plain window, as the dummy driver has no
renderer for ``GameEngine``'s SCALED one.
"""

from bitmappy.editor import BitmapEditorScene
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine, command_line

WINDOWED_ARGUMENTS = ('--windowed', '--resolution', '800x600', '--log-level', 'warning')


def make_engine(*arguments: str) -> GoldenTraceEngine:
    """Make a real engine, as the current context's, from Bitmappy's command line.

    Args:
        arguments: The arguments, after the windowed run's own.

    Returns:
        The engine, not started.

    """
    with command_line([*WINDOWED_ARGUMENTS, *arguments]):
        return GoldenTraceEngine(game=BitmapEditorScene)
