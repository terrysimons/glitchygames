#!/usr/bin/env python3
"""Basic example game."""

from __future__ import annotations

import logging
import typing
from typing import Literal, Self

if typing.TYPE_CHECKING:
    import argparse

import pygame
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

LOG: logging.Logger = logging.getLogger("game")
LOG.setLevel(logging.DEBUG)


class Game(Scene):
    """The main game class."""

    # Set your game name/version here.
    NAME: Literal["Basic App"] = "Basic App"
    VERSION: Literal["1.0"] = "1.0"
    log: logging.Logger = LOG

    def __init__(self: Self, options: dict, groups: pygame.sprite.Group | None = None) -> None:
        """Initialize the Game.

        Args:
            options (dict): The options passed to the game.
            groups (pygame.sprite.Group | None): The sprite groups to add the sprite to.

        Returns:
            None

        """
        if groups is None:
            groups = pygame.sprite.Group()

        super().__init__(options=options, groups=groups)
        # These are set up in the GameEngine class.
        self.log.info(f"Game Options: {options}")
        self.fps: Literal[6] = 6

        self.background_color = (255, 255, 0)

        self.next_scene = self

    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> None:
        """Add game-specific arguments to the gloal parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None

        """
        parser.add_argument(
            "-v", "--version", action="store_true", help="print the game version and exit"
        )

    def update(self: Self) -> None:
        """Update the scene.

        This method will get called automatically by the GameEngine class.

        Args:
            None

        Returns:
            None

        """
        # Do your updates here
        super().update()

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.info(f"Left Mouse Up: {event}")


def main() -> None:
    """Run the main entry point for the game."""
    GameEngine(game=Game).start()


if __name__ == "__main__":
    main()
