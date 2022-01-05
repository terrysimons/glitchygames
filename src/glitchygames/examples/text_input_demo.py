#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time

import pygame

from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite
from glitchygames.engine import GameEngine

LOG = logging.getLogger('game')
LOG.setLevel(logging.DEBUG)


class InputBox(Sprite):
    def __init__(self, x, y, width, height, color=(233, 248, 215), text='', name=None,
                 parent=None, groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)
        pygame.font.init()
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.font = pygame.font.SysFont('Times', 14)
        self.text = text
        self.text_image = self.font.render(self.text, True, self.color)
        self.active = True
        self.image = pygame.Surface((self.width, self.height))
        self.image.convert()
        self.parent = parent

        self.cursor_rect = self.text_image.get_rect()

        self.cursor = pygame.Rect(
            self.cursor_rect.topright,
            (3, self.cursor_rect.height)
        )

        self.dirty = 2

    def activate(self):
        self.active = True
        self.dirty = 2

    def deactivate(self):
        self.active = False
        self.dirty = 0

    def on_input_box_submit_event(self):
        if self.parent:
            try:
                self.parent.on_input_box_submit_event(self)
            except AttributeError:
                self.log.info(f'{self.name}: Submitted "{self.text}" but no parent is configured.')

    def update(self):
        self.image.fill((0, 0, 0))
        self.image.blit(self.text_image, (4, 4))

        pygame.draw.rect(self.image, self.color, (0, 0, self.rect.width, self.rect.height), 1)

        # Blit the  cursor
        if time.time() % 1 > 0.5 and self.active:
            self.cursor_rect = self.text_image.get_rect(topleft=(5, 2))

            self.cursor.midleft = self.cursor_rect.midright

            pygame.draw.rect(self.image, self.color, self.cursor)

    def render(self):
        self.text_image = self.font.render(self.text, True, (255, 255, 255))

    def on_mouse_up_event(self, event):
        self.activate()

    def on_key_up_event(self, event):
        if self.active:
            pygame.key.set_repeat(200)

            if event.key == pygame.K_TAB or event.key == pygame.K_ESCAPE:
                self.deactivate()

    def on_key_down_event(self, event):
        if self.active:
            if event.key == pygame.K_TAB:
                pass
            elif event.key == pygame.K_ESCAPE:
                pass
            elif event.key == pygame.K_RETURN:
                self.log.debug(f'Text Submitted: {self.name}: {self.text}')
                self.on_input_box_submit_event()
                self.text = ''
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                self.text += event.unicode

                self.cursor_rect.size = self.text_image.get_size()
                self.cursor.topleft = self.cursor_rect.topright

                # Limit characters           -20 for border width
                if self.text_image.get_width() > self.rect.width - 15:
                    self.text = self.text[:-1]
            self.log.debug(f'{self.name}: {self.text}')


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
        self.input_box.render()
        self.input_box.update()
        self.screen.blit(self.input_box.image, (320, 240))

    def on_input_box_submit_event(self, control):
        self.log.info(f'Got text input from: {control.name}: {control.text}')

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
