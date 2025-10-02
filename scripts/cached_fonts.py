#!/usr/bin/env python3
"""Cached Font Demo."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse


import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.sprites import BitmappySprite

LOG = logging.getLogger("game")
LOG.setLevel(logging.DEBUG)

# Turn on sprite debugging
BitmappySprite.DEBUG = True


class GameScene(Scene):
    """The intro scene."""

    log = LOG

    def __init__(self: Self, groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize the intro scene.

        Args:
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(groups=groups)
        self.all_sprites = groups
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        self.screen.fill((255, 255, 0))

        self.all_sprites.clear(self.screen, self.background)


class Game(Scene):
    """The main game class."""

    # Set your game name/version here.
    NAME = "Cached Font Demo"
    VERSION = "1.0"

    def __init__(self: Self, options: dict) -> None:
        """Initialize the Game.

        Args:
            options (dict): The options passed to the game.

        Returns:
            None

        """
        super().__init__(options=options)

        # GameEngine.OPTIONS is set on initialization.
        self.log.info(f"Game Options: {options}")

        self.next_scene = GameScene()

    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> None:
        """Add arguments to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None

        """
        parser.add_argument(
            "-v", "--version", action="store_true", help="print the game version and exit"
        )


def main() -> None:
    """Start the game."""
    GameEngine(game=Game).start()


if __name__ == "__main__":
    main()
