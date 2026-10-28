"""``python -m glitchygames`` and the ``glitchygames`` console script: the engine's tools.

Both start here (``[project.scripts]`` names ``glitchygames.__main__:main``), so pygame's banner
is hidden before anything imports pygame: the command's tools live in ``glitchygames.replay``,
whose package imports pygame, and a console script entry point in that package would import
pygame before its own module could hide the banner. The command itself is
glitchygames/replay/tools/command.py.
"""

from __future__ import annotations

import os
import sys

# pygame prints its banner to standard output when first imported unless this is set; the
# command's output is its tools' (and their child games', which inherit the environment)
PYGAME_BANNER_VARIABLE = 'PYGAME_HIDE_SUPPORT_PROMPT'


def main() -> int:
    """Run the ``glitchygames`` command with this process's arguments.

    Returns:
        The command's exit status.

    """
    os.environ.setdefault(PYGAME_BANNER_VARIABLE, '1')
    # Imported here, after the banner is hidden: importing it imports pygame
    from glitchygames.replay.tools import command

    return command.main()


if __name__ == '__main__':
    sys.exit(main())
