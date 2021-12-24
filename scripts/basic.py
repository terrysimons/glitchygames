#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging

import pygame

from ghettogames.engine import GameEngine
from ghettogames.scenes import Scene

LOG = logging.getLogger('game')
LOG.setLevel(logging.DEBUG)


class Game(Scene):
    # Set your game name/version here.
    NAME = "Basic App"
    VERSION = "1.0"
    log = LOG

    def __init__(self, options, groups=pygame.sprite.LayeredDirty()):
        super().__init__(options=options, groups=groups)
        # These are set up in the GameEngine class.
        self.log.info(f'Game Options: {options}')
        self.fps = 6

        self.background_color = (255, 255, 0)

        self.next_scene = self
        self.dirty = 1

    @classmethod
    def args(cls, parser):
        parser.add_argument('-v', '--version',
                            action='store_true',
                            help='print the game version and exit')

    def update(self):
        # Do your updates here
        super().update()

    def on_left_mouse_button_up_event(self, event):
        self.log.info(f'Left Mouse Up: {event}')


def main():
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
