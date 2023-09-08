#!/usr/bin/env python3
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

LOG = logging.getLogger('game')
LOG.setLevel(logging.DEBUG)

# Turn on sprite debugging
BitmappySprite.DEBUG = True


class IntroScene(Scene):
    def __init__(self: Self) -> None:
        super().__init__()
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.all_sprites = pygame.sprite.LayeredDirty()

        self.all_sprites.clear(self.screen, self.background)


class Game(Scene):
    # Set your game name/version here.
    NAME = 'Debug App'
    VERSION = '1.0'
    log = LOG

    def __init__(self: Self, options: dict) -> None:
        super().__init__(options=options)
        # These are set up in the GameEngine class.
        self.log.info(f'Game Options: {options}')

        self.next_scene = IntroScene()

    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument('-v', '--version',
                           action='store_true',
                           help='print the game version and exit')


def main() -> None:
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()


