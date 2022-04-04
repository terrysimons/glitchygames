#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

from glitchygames.game_objects import BallSprite
from glitchygames.game_objects.paddle import HorizontalPaddle
from glitchygames.game_objects.sounds import SFX
from glitchygames.color import (
    {{cookiecutter.player1_color|upper}}
)
from glitchygames.engine import GameEngine
from glitchygames.movement import Speed
from glitchygames.scenes import Scene

log = logging.getLogger('game')
log.setLevel(logging.INFO)


class Game(Scene):
    # Set your game name/version here.
    NAME = "{{cookiecutter.name}}"
    VERSION = "{{cookiecutter.version}}"

    def __init__(self, options, groups=pygame.sprite.LayeredDirty()):
        super().__init__(options=options, groups=groups)
        self.fps = 0

        h_center = self.screen_width/2
        self.player1 = HorizontalPaddle("{{cookiecutter.player1_name}}", (80, 20), (h_center - 40, self.screen_height - 20), {{cookiecutter.player1_color|upper}}, Speed(y=10, increment=1), collision_sound=SFX.SLAP)
        self.ball = BallSprite(collision_sound=SFX.BOUNCE, edge_bounce_list=['left', 'right', 'top'])

        self.all_sprites = pygame.sprite.LayeredDirty(
            (
                self.player1,
                self.ball
            )
        )

        self.all_sprites.clear(self.screen, self.background)

    def setup(self):
        self.fps = 60
        pygame.key.set_repeat(1)

    def dt_tick(self, dt):
        self.dt = dt
        self.dt_timer += self.dt

        for sprite in self.all_sprites:
            sprite.dt_tick(dt)

    def update(self):
        if pygame.sprite.collide_rect(self.player1, self.ball) and self.ball.speed.y > 0:
            self.player1.snd.play()
            self.ball.speed.y *= -1

        super().update()

    def on_controller_button_down_event(self, event):
        if event.button in (pygame.CONTROLLER_BUTTON_DPAD_LEFT, pygame.CONTROLLER_BUTTON_DPAD_RIGHT):
            self.player1.stop()

    def on_controller_button_up_event(self, event):
        if event.button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
            self.player1.left()
        if event.button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
            self.player1.right()

    def on_controller_axis_motion_event(self, event):
        if event.axis == pygame.CONTROLLER_AXIS_LEFTY:
            if event.value < 0:
                self.player1.left()
            if event.value == 0:
                self.player1.stop()
            if event.value > 0:
                self.player1.right()

    def on_key_up_event(self, event):
        # Handle ESC/q to quit
        super().on_key_up_event(event)

        unpressed_keys = pygame.key.get_pressed()

        # KEYUP            key, mod
        if unpressed_keys[pygame.K_LEFT]:
            self.player1.stop()
        if unpressed_keys[pygame.K_RIGHT]:
            self.player1.stop()

    def on_key_down_event(self, event):
        # KEYDOWN            key, mod
        # self.log.info(f'Key Down Event: {event}')
        pressed_keys = pygame.key.get_pressed()

        if pressed_keys[pygame.K_LEFT]:
            self.player1.left()
        if pressed_keys[pygame.K_RIGHT]:
            self.player1.right()

def main():
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
