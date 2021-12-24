#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
import random

import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

from ghettogames.color import WHITE, BLACKLUCENT
from ghettogames.engine import GameEngine
from ghettogames.fonts import FontManager
from ghettogames.joysticks import JoystickManager
from ghettogames.scenes import Scene
from ghettogames.sprites import Sprite

log = logging.getLogger('game')
log.setLevel(logging.DEBUG)


class Speed:
    def __init__(self, x=0, y=0, increment=0.2):
        self.x = x
        self.y = y
        self.increment = increment

    def speed_up(self):
        self.x += self.increment if self.x >= 0 else self.increment * -1
        self.y += self.increment if self.y >= 0 else self.increment * -1


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


class PaddleSprite(Sprite):
    def __init__(self, x=0, y=320, width=20, height=80,
                 name='Player 1', groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)
        self.use_gfxdraw = True
        # Adding some slap to the paddle
        self.slap_snd = pygame.mixer.Sound(
            os.path.join(
                os.path.dirname(__file__),
                'resources/snd/slap8.wav'
            )
        )

        self.name = name
        self.screen = pygame.display.get_surface()
        self.screen_rect = self.screen.get_rect()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.width = width
        self.height = height
        self.image = pygame.Surface((self.width, self.height))
        self.image.convert()
        self.rect = self.image.get_rect()

        pygame.draw.rect(self.image, WHITE, (0, 0, self.width, self.height), 0)
        self.rect.x = x
        self.rect.y = y
        self.moving = False
        self.speed = Speed()

        self.dirty = 1

    def update(self):
        # This prevents us from having the paddle bounce
        # at the edges.
        if self.rect.bottom + self.speed.y > self.screen_rect.bottom:
            self.rect.y = self.screen_rect.bottom - self.height
            self.stop()
        elif self.rect.top + self.speed.y < self.screen_rect.top:
            self.rect.y = 0
            self.stop()
        else:
            self.rect.y += self.speed.y

        self.dirty = 1

    def move_down(self):
        self.speed.y = 10
        self.dirty = 1

    def move_up(self):
        self.speed.y = -10
        self.dirty = 1

    def stop(self):
        self.speed.x = 0
        self.speed.y = 0
        self.dirty = 1


class BallSprite(Sprite):
    def __init__(self, x=0, y=0, width=20, height=20, groups=pygame.sprite.LayeredDirty()):
        super().__init__(x=x, y=y, width=width, height=height, groups=groups)
        self.use_gfxdraw = True
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.width = width
        self.height = height
        self.image = pygame.Surface((self.width, self.height))
        self.image.convert()
        self.image.set_colorkey(0)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.direction = 0
        self.speed = Speed(4, 2)
        self.rally = Rally(5, self.speed.speed_up)
        self.collision_snd = pygame.mixer.Sound(
            os.path.join(
                os.path.dirname(__file__),
                'resources/snd/sfx_menu_move1.wav'
            )
        )

        pygame.draw.circle(self.image,
                           WHITE,
                           (self.width // 2, self.height // 2),
                           5,
                           0)

        self.reset()

        # The ball always needs refreshing.
        # This saves us a set on dirty every update.
        self.dirty = 2

    def _do_bounce(self):
        if self.rect.y <= 0:
            self.collision_snd.play()
            self.rect.y = 0
            self.speed.y *= -1
        if self.rect.y + self.height >= self.screen_height:
            self.collision_snd.play()
            self.rect.y = self.screen_height - self.height
            self.speed.y *= -1

    def reset(self):
        self.x = random.randrange(50, 750)
        self.y = random.randrange(25, 400)

        # Direction of ball (in degrees)
        self.direction = random.randrange(-45, 45)

        # Flip a 'coin'
        if random.randrange(2) == 0:
            # Reverse ball direction, let the other guy get it first
            self.direction += 180

        self.rally.reset()

        self.rect.x = self.x
        self.rect.y = self.y

    # This function will bounce the ball off a horizontal surface (not a vertical one)
    def bounce(self, diff):
        self.direction = (180 - self.direction) % 360
        self.direction -= diff

        # Speed the ball up
        self.speed *= 1.1

    def update(self):
        self.rect.y += self.speed.y
        self.rect.x += self.speed.x

        self._do_bounce()

        if self.rect.x > self.screen_width or self.rect.x < 0:
            self.reset()

        if self.y > self.screen_height or self.rect.y < 0:
            self.reset()

        # Do we bounce off the left of the screen?
        if self.x <= 0:
            self.direction = (360 - self.direction) % 360
            self.x = 1

        # Do we bounce of the right side of the screen?
        if self.x > self.screen_width - self.width:
            self.direction = (360 - self.direction) % 360


class TextSprite(Sprite):
    def __init__(self, background_color=BLACKLUCENT, alpha=0, x=0, y=0,
                 groups=pygame.sprite.LayeredDirty()):
        super().__init__(groups=groups)
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

        # Interiting from object is default in Python 3.
        # Linters complain if you do it.
        class TextBox(Sprite):
            def __init__(self, font_controller, pos, line_height=15,
                         groups=pygame.sprite.LayeredDirty()):
                super().__init__(groups=groups)
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
        self.fps = 60

        self.player1 = PaddleSprite(name="Player 1",)
        self.player2 = PaddleSprite(name="Player 2")
        self.ball = BallSprite()

        # Set player 2's position on the right side of the screen.
        self.player2.rect.x = self.player2.screen.get_width() - self.player2.width

        self.all_sprites = pygame.sprite.LayeredDirty(
            (
                self.player1,
                self.player2,
                self.ball
            )
        )

        self.all_sprites.clear(self.screen, self.background)
        self.dirty = 1

        self.next_scene = self

    @classmethod
    def args(cls, parser):
        parser.add_argument('-v', '--version',
                            action='store_true',
                            help='print the game version and exit')

    def update(self):
        super().update()

        if pygame.sprite.collide_rect(self.player1, self.ball) and self.ball.speed.x <= 0:
            self.ball.rally.hit()
            if self.ball.rally.do_rally():
                self.ball.rally.reset()

            self.player1.slap_snd.play()
            self.ball.speed.x *= -1

        if pygame.sprite.collide_rect(self.player2, self.ball) and self.ball.speed.x > 0:
            self.ball.rally.hit()
            if self.ball.rally.do_rally():
                self.ball.rally.reset()

            self.player2.slap_snd.play()
            self.ball.speed.x *= -1

        self.dirty = 1

    def on_key_up_event(self, event):
        # Handle ESC/q to quit
        super().on_key_up_event(event)

        # KEYUP            key, mod
        if event.key == pygame.K_UP:
            self.player1.stop()
        if event.key == pygame.K_DOWN:
            self.player1.stop()
        if event.key == pygame.K_w:
            self.player2.stop()
        if event.key == pygame.K_s:
            self.player2.stop()

    def on_key_down_event(self, event):
        # KEYDOWN            key, mod
        if event.key == pygame.K_UP:
            self.player1.move_up()
        if event.key == pygame.K_DOWN:
            self.player1.move_down()
        if event.key == pygame.K_w:
            self.player2.move_up()
        if event.key == pygame.K_s:
            self.player2.move_down()


def main():
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
