#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import random

import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

from glitchygames.color import WHITE, BLACKLUCENT
from glitchygames.engine import GameEngine
from glitchygames.fonts import FontManager
from glitchygames.events.joystick import JoystickManager
from glitchygames.game_objects import BallSprite
from glitchygames.game_objects.paddle import VerticalPaddle
from glitchygames.game_objects.sounds import SFX
from glitchygames.movement import Speed
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite

log = logging.getLogger('game')
log.setLevel(logging.INFO)


class Rally:
    def __init__(self, trigger_value, action):
        self._trigger_value = trigger_value
        self._action = action
        self._count = 0

    def hit(self):
        self._count += 1

    def reset(self):
        self._count = 0

    def do_rally(self):
        if self._trigger_value == self._count:
            self._action()
            return True
        return False


class TextSprite(Sprite):
    def __init__(self, background_color=BLACKLUCENT, alpha=0, x=0, y=0,
                 groups=pygame.sprite.LayeredDirty()):
        super().__init__(x, y, 0, 0, groups=groups)
        self.background_color = background_color
        self.alpha = alpha
        self.x = x
        self.y = y

        # Quick and dirty, for now.
        self.image = pygame.Surface((400, 400))
        self.screen = pygame.display.get_surface()

        if not alpha:
            self.image.set_colorkey(self.background_color)
            self.image.convert()
        else:
            # Enabling set_alpha() and also setting a color
            # key will let you hide the background
            # but things that are blited otherwise will
            # be translucent.  This can be an easy
            # hack to get a translucent image which
            # does not have a border, but it causes issues
            # with edge-bleed.
            #
            # What if we blitted the translucent background
            # to the screen, then copied it and used the copy
            # to write the text on top of when translucency
            # is set?  That would allow us to also control
            # whether the text is opaque or translucent, and
            # it would also allow a different translucency level
            # on the text than the window.
            self.image.convert_alpha()
            self.image.set_alpha(self.alpha)

        self.rect = self.image.get_rect()
        self.rect.x += x
        self.rect.y += y
        self.font_manager = FontManager()
        self.joystick_manager = JoystickManager()
        self.joystick_count = len(self.joystick_manager.joysticks)

        # Inheriting from object is default in Python 3.
        # Linters complain if you do it.
        class TextBox(Sprite):
            def __init__(self, font_controller, pos, line_height=15,
                         groups=pygame.sprite.LayeredDirty()):
                super().__init__(pos[0], pos[1], 0, 0, groups=groups)
                self.image = None
                self.start_pos = pos
                self.rect = pygame.Rect(pos, (640, 480))
                self.line_height = line_height

                pygame.freetype.set_default_resolution(font_controller.font_dpi)
                self.font = pygame.freetype.SysFont(name=font_controller.font,
                                                    size=font_controller.font_size)

            def print(self, surface, string):
                (self.image, self.rect) = self.font.render(string, WHITE)
                # self.image
                surface.blit(self.image, self.rect.center)
                self.rect.center = surface.get_rect().center
                self.rect.y += self.line_height

            def reset(self):
                self.rect.center = self.start_pos

            def indent(self):
                self.rect.x += 10

            def unindent(self):
                self.rect.x -= 10

        self.text_box = TextBox(font_controller=self.font_manager, pos=self.rect.center)
        self.dirty = 2

    def update(self):
        self.image.fill(self.background_color)

        self.text_box.reset()
        self.text_box.print(self.image, f'{Game.NAME} version {Game.VERSION}')


class Game(Scene):
    # Set your game name/version here.
    NAME = "Paddle Slap"
    VERSION = "1.1"

    def __init__(self, options, groups=pygame.sprite.LayeredDirty()):
        super().__init__(options=options, groups=groups)
        self.fps = 0

        v_center = self.screen_height / 2
        self.player1 = VerticalPaddle(
            'Player 1',
            (20, 80),
            (0, v_center - 40),
            WHITE,
            Speed(y=10, increment=1),
            collision_sound=SFX.SLAP
        )
        self.player2 = VerticalPaddle(
            'Player 2',
            (20, 80),
            (self.screen_width - 20, v_center - 40),
            WHITE,
            Speed(y=10, increment=1),
            collision_sound=SFX.SLAP
        )
        self.balls = [
            BallSprite(collision_sound=SFX.BOUNCE) for _ in range(self.options.get('balls', 1))
        ]

        for ball in self.balls:
            red = random.randint(0, 255)
            green = random.randint(0, 255)
            blue = random.randint(0, 255)
            ball.color = (red, green, blue)

        self.all_sprites = pygame.sprite.LayeredDirty(
            (
                self.player1,
                self.player2,
                *self.balls
            )
        )

        self.all_sprites.clear(self.screen, self.background)

    @classmethod
    def args(cls, parser):
        parser.add_argument('-v', '--version',
                            action='store_true',
                            help='print the game version and exit')

        parser.add_argument('-b', '--balls',
                            type=int,
                            help='the number of balls to start with',
                            default=1)

    def setup(self):
        self.fps = 60
        pygame.key.set_repeat(1)

    def dt_tick(self, dt):
        self.dt = dt
        self.dt_timer += self.dt

        for sprite in self.all_sprites:
            sprite.dt_tick(dt)

    def update(self):
        for ball in self.balls:
            if pygame.sprite.collide_rect(self.player1, ball) and ball.speed.x <= 0:
                # ball.rally.hit()
                # if ball.rally.do_rally():
                #     ball.rally.reset()

                self.player1.snd.play()
                ball.speed.x *= -1

            if pygame.sprite.collide_rect(self.player2, ball) and ball.speed.x > 0:
                # ball.rally.hit()
                # if ball.rally.do_rally():
                #     ball.rally.reset()

                self.player2.snd.play()
                ball.speed.x *= -1

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
