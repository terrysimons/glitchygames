#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

from glitchygames.game_objects import BallSprite
from glitchygames.game_objects.paddle import VerticalPaddle
from glitchygames.game_objects.sounds import SFX
from glitchygames.color import (
    {{cookiecutter.player1_color|upper}},
    {{cookiecutter.player2_color|upper}},
    {{cookiecutter.background|upper}}
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

        v_center = self.screen_height/2
        self.player1 = VerticalPaddle("{{cookiecutter.player1_name}}", (20, 80), (0, v_center - 40), {{cookiecutter.player1_color|upper}}, Speed(y=10, increment=1), collision_sound=SFX.SLAP)
        self.player2 = VerticalPaddle("{{cookiecutter.player2_name}}", (20, 80), (self.screen_width - 20, v_center - 40), {{cookiecutter.player2_color|upper}}, Speed(y=10, increment=1), collision_sound=SFX.SLAP)
        self.ball = BallSprite(collision_sound=SFX.BOUNCE)

        self.all_sprites = pygame.sprite.LayeredDirty(
            (
                self.player1,
                self.player2,
                self.ball
            )
        )

        self.all_sprites.clear(self.screen, self.background)

    @classmethod
    def args(cls, parser):
        parser.add_argument('-v', '--version',
                            action='store_true',
                            help='print the game version and exit')

    def setup(self):
        self.fps = 60
        pygame.key.set_repeat(1)

    def dt_tick(self, dt):
        self.dt = dt
        self.dt_timer += self.dt

        for sprite in self.all_sprites:
            sprite.dt_tick(dt)

    def update(self):
        if pygame.sprite.collide_rect(self.player1, self.ball) and self.ball.speed.x <= 0:
            self.player1.snd.play()
            self.ball.speed.x *= -1

        if pygame.sprite.collide_rect(self.player2, self.ball) and self.ball.speed.x > 0:
            self.player2.snd.play()
            self.ball.speed.x *= -1

        super().update()

    def on_controller_button_down_event(self, event):

        if event.button in (pygame.CONTROLLER_BUTTON_DPAD_UP, pygame.CONTROLLER_BUTTON_DPAD_DOWN):
            player = self.player1 if event.instance_id == 0 else self.player2
            player.stop()

        self.log.info(f'GOT on_controller_button_down_event: {event}')

    def on_controller_button_up_event(self, event):

        player = self.player1 if event.instance_id == 0 else self.player2
        if event.button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            player.up()
        if event.button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            player.down()

        self.log.info(f'GOT on_controller_button_up_event: {event}')

    def on_controller_axis_motion_event(self, event):

        player = self.player1 if event.instance_id == 0 else self.player2
        if event.axis == pygame.CONTROLLER_AXIS_LEFTY:
            if event.value < 0:
                player.up()
            if event.value == 0:
                player.stop()
            if event.value > 0:
                player.down()
            self.log.info(f'GOT on_controller_axis_motion_event: {event}')

    def on_key_up_event(self, event):
        # Handle ESC/q to quit
        super().on_key_up_event(event)

        unpressed_keys = pygame.key.get_pressed()

        # KEYUP            key, mod
        if unpressed_keys[pygame.K_UP]:
            self.player1.stop()
        if unpressed_keys[pygame.K_DOWN]:
            self.player1.stop()
        if unpressed_keys[pygame.K_w]:
            self.player2.stop()
        if unpressed_keys[pygame.K_s]:
            self.player2.stop()

    def on_key_down_event(self, event):
        # KEYDOWN            key, mod
        # self.log.info(f'Key Down Event: {event}')
        pressed_keys = pygame.key.get_pressed()

        if pressed_keys[pygame.K_w]:
            self.player1.up()
        if pressed_keys[pygame.K_s]:
            self.player1.down()
        if pressed_keys[pygame.K_UP]:
            self.player2.up()
        if pressed_keys[pygame.K_DOWN]:
            self.player2.down()


def main():
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
