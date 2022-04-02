#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
import random
import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

from glitchygames.color import (
    {{cookiecutter.player1_color|upper}},
    {{cookiecutter.player2_color|upper}},
    {{cookiecutter.background|upper}}
)
from glitchygames.engine import GameEngine
from glitchygames.fonts import FontManager
from glitchygames.events.joystick import JoystickManager
from glitchygames.movement import Vertical
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite

log = logging.getLogger('game')
log.setLevel(logging.INFO)


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
                 name='{{cookiecutter.player1_name}}', groups=pygame.sprite.LayeredDirty(), color={{cookiecutter.player1_color|upper}}):
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

        pygame.draw.rect(self.image, color, (0, 0, self.width, self.height), 0)
        self.rect.x = x
        self.rect.y = y
        self.moving = False
        self.speed = Speed()
        self.move = Vertical(self, 10)
        self.dirty = 1

    def update(self):
        # This prevents us from having the paddle bounce
        # at the edges.
        self.move.detect_edge()


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
        self.color = {{cookiecutter.player1_color|upper}}

        self.reset()

        # The ball always needs refreshing.
        # This saves us a set on dirty every update.
        self.dirty = 2

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, new_color):
        self._color = new_color
        pygame.draw.circle(
            self.image,
            self._color,
            (self.width // 2, self.height // 2),
            5,
            0
        )

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
    def __init__(self, background_color={{cookiecutter.background|upper}}, alpha=0, x=0, y=0,
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
                (self.image, self.rect) = self.font.render(string, {{cookiecutter.player1_color|upper}})
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
    NAME = "{{cookiecutter.name}}"
    VERSION = "{{cookiecutter.version}}"

    def __init__(self, options, groups=pygame.sprite.LayeredDirty()):
        super().__init__(options=options, groups=groups)
        self.fps = 0

        self.player1 = PaddleSprite(name="{{cookiecutter.player1_name}}", color={{cookiecutter.player1_color|upper}})
        self.player2 = PaddleSprite(name="{{cookiecutter.player2_name}}", color={{cookiecutter.player2_color|upper}})
        self.balls = [BallSprite() for _ in range(self.options.get('balls', 1))]

        for ball in self.balls:
            red = random.randint(0, 255)
            green = random.randint(0, 255)
            blue = random.randint(0, 255)
            ball.color = (red, green, blue)

        # Set player 2's position on the right side of the screen.
        self.player2.rect.x = self.player2.screen.get_width() - self.player2.width

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
                ball.rally.hit()
                if ball.rally.do_rally():
                    ball.rally.reset()

                self.player1.slap_snd.play()
                ball.speed.x *= -1

            if pygame.sprite.collide_rect(self.player2, ball) and ball.speed.x > 0:
                ball.rally.hit()
                if ball.rally.do_rally():
                    ball.rally.reset()

                self.player2.slap_snd.play()
                ball.speed.x *= -1

        super().update()

    def on_controller_button_down_event(self, event):

        if event.button in (pygame.CONTROLLER_BUTTON_DPAD_UP, pygame.CONTROLLER_BUTTON_DPAD_DOWN):
            player = self.player1 if event.instance_id == 0 else self.player2
            player.move.stop()

        self.log.info(f'GOT on_controller_button_down_event: {event}')

    def on_controller_button_up_event(self, event):

        player = self.player1 if event.instance_id == 0 else self.player2
        if event.button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            player.move.up()
        if event.button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            player.move.down()

        self.log.info(f'GOT on_controller_button_up_event: {event}')

    def on_controller_axis_motion_event(self, event):

        player = self.player1 if event.instance_id == 0 else self.player2
        if event.axis == pygame.CONTROLLER_AXIS_LEFTY:
            if event.value < 0:
                player.move.up()
            if event.value == 0:
                player.move.stop()
            if event.value > 0:
                player.move.down()
            self.log.info(f'GOT on_controller_axis_motion_event: {event}')

    def on_key_up_event(self, event):
        # Handle ESC/q to quit
        super().on_key_up_event(event)

        unpressed_keys = pygame.key.get_pressed()

        # KEYUP            key, mod
        if unpressed_keys[pygame.K_UP]:
            self.player1.move.stop()
        if unpressed_keys[pygame.K_DOWN]:
            self.player1.move.stop()
        if unpressed_keys[pygame.K_w]:
            self.player2.move.stop()
        if unpressed_keys[pygame.K_s]:
            self.player2.move.stop()

    def on_key_down_event(self, event):
        # KEYDOWN            key, mod
        # self.log.info(f'Key Down Event: {event}')
        pressed_keys = pygame.key.get_pressed()

        if pressed_keys[pygame.K_w]:
            self.player1.move.up()
        if pressed_keys[pygame.K_s]:
            self.player1.move.down()
        if pressed_keys[pygame.K_UP]:
            self.player2.move.up()
        if pressed_keys[pygame.K_DOWN]:
            self.player2.move.down()


def main():
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
