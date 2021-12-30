#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging

import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

from glitchygames.engine import GameEngine
from glitchygames.sprites import BitmappySprite
from glitchygames.scenes import Scene

LOG = logging.getLogger('game')
LOG.setLevel(logging.DEBUG)

# Turn on sprite debugging
BitmappySprite.DEBUG = True


class GameScene(Scene):
    log = LOG

    def __init__(self, groups=pygame.sprite.LayeredDirty()):
        super().__init__(groups=groups)
        self.all_sprites = groups
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        self.screen.fill((255, 255, 0))

        self.all_sprites.clear(self.screen, self.background)


class Game(Scene):
    # Set your game name/version here.
    NAME = "Cached Font Demo"
    VERSION = "1.0"

    def __init__(self, options):
        super().__init__(options=options)

        # GameEngine.OPTIONS is set on initialization.
        self.log.info(f'Game Options: {options}')

        self.next_scene = GameScene()

    @classmethod
    def args(cls, parser):
        parser.add_argument('-v', '--version',
                            action='store_true',
                            help='print the game version and exit')


def main():
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
