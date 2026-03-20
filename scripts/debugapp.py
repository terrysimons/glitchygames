#!/usr/bin/env python3
"""Debug App."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    import argparse

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.sprites import BitmappySprite

LOG = logging.getLogger('game')
LOG.setLevel(logging.DEBUG)

# Turn on sprite debugging
BitmappySprite.DEBUG = True


class IntroScene(Scene):
    """The intro scene."""

    def __init__(self: Self) -> None:
        """Initialize the intro scene."""
        super().__init__()
        screen = pygame.display.get_surface()
        assert screen is not None
        self.screen: pygame.Surface = screen
        self.screen_width: int = self.screen.get_width()
        self.screen_height: int = self.screen.get_height()
        self.all_sprites: pygame.sprite.LayeredDirty[Any] = pygame.sprite.LayeredDirty()

        self.all_sprites.clear(self.screen, self.background)


class Game(Scene):
    """The main game class."""

    # Set your game name/version here.
    NAME = 'Debug App'
    VERSION = '1.0'
    log = LOG

    def __init__(self: Self, options: dict[str, Any]) -> None:
        """Initialize the Game.

        Args:
            options (dict[str, Any]): The options passed to the game.

        """
        super().__init__(options=options)
        # These are set up in the GameEngine class.
        self.log.info(f'Game Options: {options}')

        self.next_scene = IntroScene()

    @classmethod
    def args(cls: type[Game], parser: argparse.ArgumentParser) -> None:
        """Add arguments to the parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        """
        parser.add_argument(
            '-v', '--version', action='store_true', help='print the game version and exit'
        )


def main() -> None:
    """Run the game."""
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
