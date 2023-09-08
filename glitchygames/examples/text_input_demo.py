#!/usr/bin/env python3
from __future__ import annotations

import logging
from typing import Self

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.ui import InputBox

LOG = logging.getLogger('game')
LOG.setLevel(logging.DEBUG)


class Game(Scene):
    log = LOG

    # Set your game name/version here.
    NAME = 'Input Demo'
    VERSION = '1.0'

    def __init__(self: Self, options: dict, groups: pygame.sprite.LayeredDirty = pygame.sprite.LayeredDirty()) -> None:  # noqa: E501
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

    def setup(self: Self) -> None:
        pygame.key.set_repeat(350)

    def update(self: Self) -> None:
        self.input_box.update()
        self.screen.blit(self.input_box.image, (320, 240))

    def on_input_box_submit_event(self: Self, control: object) -> None:
        self.log.info(f'{self.name} Got text input from: {control.name}: {control.text}')

    def on_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        self.input_box.activate()

    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        if self.input_box.active:
            self.input_box.on_key_up_event(event)
        elif event.key == pygame.K_TAB:
            self.input_box.activate()
        else:
            super().on_key_up_event(event)

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        if self.input_box.active:
            self.input_box.on_key_down_event(event)
        else:
            super().on_key_up_event(event)


def main() -> None:
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
