from pygame.sprite import LayeredDirty
from pygame import draw
from . import load_sound
from glitchygames.sprites import Sprite
from glitchygames.movement import (
    Horizontal,
    Vertical
)


class BasePaddle(Sprite):

    def __init__(self, axis, speed, name, color, x, y, width, height, groups, collision_sound):
        super().__init__(name=name, x=x, y=y, width=width, height=height, groups=groups)

        self.use_gfxdraw = True
        self.moving = False

        self.image.convert()
        draw.rect(self.image, color, (0, 0, self.width, self.height))
        if collision_sound:
            self.snd = load_sound(collision_sound)
        self._move = axis(speed)
        self.dirty = 1

    def move_horizontal(self):
        self.rect.x += self._move.current_speed
        self.dirty = 1

    def move_vertical(self):
        self.rect.y += self._move.current_speed
        self.dirty = 1

    def is_at_bottom_of_screen(self):
        return self.rect.bottom + self._move.current_speed > self.screen_height

    def is_at_top_of_screen(self):
        return self.rect.top + self._move.current_speed < 0

    def is_at_left_of_screen(self):
        return self.rect.left + self._move.current_speed < self.screen.left

    def is_at_right_of_screen(self):
        return self.rect.right + self._move.current_speed > self.screen.right


class HorizontalPaddle(BasePaddle):

    def __init__(self, name, size, position, color, speed, groups=LayeredDirty(), collision_sound=None):
        super().__init__(Horizontal, speed, name, color, position[0], position[1], size[0], size[1],
                         groups,
                         collision_sound)

    def update(self):
        if self.is_at_left_of_screen():
            self.rect.x = 0
            self.stop()
        elif self.is_at_right_of_screen():
            self.rect.x = self.screen.right - self.rect.width
            self.stop()
        else:
            self.move_horizontal()

    def left(self):
        self._move.left()
        self.dirty = 1

    def right(self):
        self._move.right()
        self.dirty = 1

    def stop(self):
        self._move.stop()
        self.dirty = 1

    def speed_up(self):
        self._move.speed.speed_up_horizontal()


class VerticalPaddle(BasePaddle):

    def __init__(self, name, size, position, color, speed, groups=LayeredDirty(), collision_sound=None):
        super().__init__(Vertical, speed, name, color, position[0], position[1], size[0], size[1],
                         groups,
                         collision_sound)

    def update(self):
        if self.is_at_top_of_screen():
            self.rect.y = 0
            self.stop()
        elif self.is_at_bottom_of_screen():
            self.rect.y = self.screen_height - self.rect.height
            self.stop()
        else:
            self.move_vertical()

    def up(self):
        self._move.up()
        self.dirty = 1

    def down(self):
        self._move.down()
        self.dirty = 1

    def stop(self):
        self._move.stop()
        self.dirty = 1

    def speed_up(self):
        self._move.speed.speed_up_vertical()
