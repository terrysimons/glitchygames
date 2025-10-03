#!/usr/bin/env python3
"""Bitrot Adventures."""

import argparse
import logging
from typing import NoReturn, Self

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

# Instantiate a logger called "game" to enable glitchygames
# logging module. This is optional, but recommended.
LOG = logging.getLogger("game")


# Think of a scene as an encapsulated pygame screen.
#
# Each scene can handle its own events, update its own
# state, and draw its own graphics.
#
# The engine will handle switching between scenes
# and passing events to the current scene.
#
# The engine will also handle drawing the current
# scene to the screen.
class BitrotAdventures(Scene):
    """Draws a pixel to the screen."""

    NAME = "Bitrot Adventures"
    VERSION = "0.0.0"

    def __init__(self: Self, options: dict[str, str]) -> Self:
        """Initialize the scene.

        Args:
            options (dict[str, str]): Game options.

        """
        super().__init__(options=options)

    # This is called by glitchygames.GameEngine before
    # the class is instantiated.
    #
    # Note that GameEngine defines a few command line
    # options that are intended to be common across all
    # games, so it's worth checking your game with --help
    # before adding new options to ensure that you haven't
    # clobbered an existing option.
    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Game specific command line arguments."""
        parser.add_argument("-s", "--some-game-specific-option", help="foo help")
        return parser


def main() -> NoReturn:
    """Run the game."""
    # Note that the Scene (BitrotAdventures) is
    # passed in uninitialized - the engine
    # will initialize it for you.
    GameEngine(game=BitrotAdventures, icon="/path/to/icon").start()


if __name__ == "__main__":
    main()
