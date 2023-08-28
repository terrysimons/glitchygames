import random

import pygame

from glitchygames import game_objects
from glitchygames.color import WHITE
from glitchygames.movement import Speed
from glitchygames.sprites import Sprite


class BallSprite(Sprite):

    def __init__(self, x=0, y=0, width=20, height=20, groups=pygame.sprite.LayeredDirty(),
                 collision_sound=None):
        super().__init__(x=x, y=y, width=width, height=height, groups=groups)
        self.use_gfxdraw = True
        self.image.convert()
        self.image.set_colorkey(0)
        self.direction = 0
        self.speed = Speed(4, 2)
        if collision_sound:
            self.snd = game_objects.load_sound(collision_sound)
        self.color = WHITE

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
            self.snd.play()
            self.rect.y = 0
            self.speed.y *= -1
        if self.rect.y + self.height >= self.screen_height:
            self.snd.play()
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

        # self.rally.reset()

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
