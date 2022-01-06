#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.ui import InputBox

LOG = logging.getLogger('game')
LOG.setLevel(logging.DEBUG)


class Game(Scene):
    log = LOG

    # Set your game name/version here.
    NAME = "Input Demo"
    VERSION = "1.0"

    def __init__(self, options, groups=pygame.sprite.LayeredDirty()):
        super().__init__(options=options, groups=groups)

        self.input_box = InputBox(
            x=320,
            y=240,
            width=200,
            height=20,
            text='Test',
            parent=self,
            groups=groups
        )

        self.background_color = (255, 255, 0)

        self.all_sprites = pygame.sprite.LayeredDirty(
            self.input_box
        )

        self.all_sprites.clear(self.screen, self.background)

    def setup(self):
        pygame.key.set_repeat(350)

    def update(self):
        self.input_box.update()
        self.screen.blit(self.input_box.image, (320, 240))

    def on_input_box_submit_event(self, control):
        self.log.info(f'{self.name} Got text input from: {control.name}: {control.text}')

    def on_mouse_button_up_event(self, event):
        self.input_box.activate()

    def on_key_up_event(self, event):
        if self.input_box.active:
            self.input_box.on_key_up_event(event)
        else:
            if event.key == pygame.K_TAB:
                self.input_box.activate()
            else:
                super().on_key_up_event(event)

    def on_key_down_event(self, event):
        if self.input_box.active:
            self.input_box.on_key_down_event(event)
        else:
            super().on_key_up_event(event)


def main():
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
