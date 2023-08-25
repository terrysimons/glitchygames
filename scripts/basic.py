#!/usr/bin/env python3
from __future__ import annotations

import logging
from typing import Literal

import pygame
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

LOG: logging.Logger = logging.getLogger('game')
LOG.setLevel(logging.DEBUG)


class Game(Scene):
    # Set your game name/version here.
    NAME: Literal['Basic App'] = 'Basic App'
    VERSION: Literal['1.0'] = '1.0'
    log: logging.Logger = LOG

    def __init__(self, options, groups=pygame.sprite.LayeredDirty()) -> None:
        super().__init__(options=options, groups=groups)
        # These are set up in the GameEngine class.
        self.log.info(f'Game Options: {options}')
        self.fps: Literal[6] = 6

        self.background_color = (255, 255, 0)

        self.next_scene = self

    @classmethod
    def args(cls, parser) -> None:
        parser.add_argument('-v', '--version',
                            action='store_true',
                            help='print the game version and exit')

    def update(self) -> None:
        # Do your updates here
        super().update()

    def on_left_mouse_button_up_event(self, event) -> None:
        self.log.info(f'Left Mouse Up: {event}')


def main() -> None:
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
