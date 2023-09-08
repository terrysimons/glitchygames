#!/usr/bin/env python3
from __future__ import annotations

import logging
from typing import Self

import pygame
from pygame import draw

from glitchygames.game_objects import load_sound
from glitchygames.movement import Horizontal, Vertical
from glitchygames.sprites import Sprite

log = logging.getLogger('game.paddle')
log.setLevel(logging.INFO)

class BasePaddle(Sprite):

    def __init__(self: Self, axis: Horizontal | Vertical, speed: int, name: str, color: tuple,
                 x: int, y: int, width: int, height: int,
                 groups: pygame.sprite.LayeredDirty | None = None,
                 collision_sound: str | None = None) -> None:
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(name=name, x=x, y=y, width=width, height=height, groups=groups)

        self.use_gfxdraw = True
        self.moving = False

        self.image.convert()
        draw.rect(self.image, color, (0, 0, self.width, self.height))
        if collision_sound:
            self.snd = load_sound(collision_sound)
        self._move = axis(speed)
        self.dirty = 1

    def move_horizontal(self: Self) -> None:
        self.rect.x += self._move.current_speed
        self.dirty = 1

    def move_vertical(self: Self) -> None:
        self.rect.y += self._move.current_speed
        self.dirty = 1

    def is_at_bottom_of_screen(self: Self) -> bool:
        return self.rect.bottom + self._move.current_speed > self.screen_height

    def is_at_top_of_screen(self: Self) -> bool:
        return self.rect.top + self._move.current_speed < 0

    def is_at_left_of_screen(self: Self) -> bool:
        return self.rect.left + self._move.current_speed < self.screen.left

    def is_at_right_of_screen(self: Self) -> bool:
        return self.rect.right + self._move.current_speed > self.screen.right


class HorizontalPaddle(BasePaddle):

    def __init__(self: Self, name: str, size: tuple, position: tuple, color: tuple,
                 speed: int, groups: pygame.sprite.LayeredDirty | None = None,
                 collision_sound: str | None = None) -> None:
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(Horizontal, speed, name, color, position[0], position[1], size[0], size[1],
                         groups,
                         collision_sound)

    def update(self: Self) -> None:
        if self.is_at_left_of_screen():
            self.rect.x = 0
            self.stop()
        elif self.is_at_right_of_screen():
            self.rect.x = self.screen.right - self.rect.width
            self.stop()
        else:
            self.move_horizontal()

    def left(self: Self) -> None:
        self._move.left()
        self.dirty = 1

    def right(self: Self) -> None:
        self._move.right()
        self.dirty = 1

    def stop(self: Self) -> None:
        self._move.stop()
        self.dirty = 1

    def speed_up(self: Self) -> None:
        self._move.speed.speed_up_horizontal()


class VerticalPaddle(BasePaddle):

    def __init__(self: Self, name: str, size: tuple, position: tuple, color: tuple,
                 speed: int, groups: pygame.sprite.LayeredDirty | None = None,
                 collision_sound: str | None = None) -> None:
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(Vertical, speed, name, color, position[0], position[1], size[0], size[1],
                         groups,
                         collision_sound)

    def update(self: Self) -> None:
        if self.is_at_top_of_screen():
            self.rect.y = 0
            self.stop()
        elif self.is_at_bottom_of_screen():
            self.rect.y = self.screen_height - self.rect.height
            self.stop()
        else:
            self.move_vertical()

    def up(self: Self) -> None:
        self._move.up()
        self.dirty = 1

    def down(self: Self) -> None:
        self._move.down()
        self.dirty = 1

    def stop(self: Self) -> None:
        self._move.stop()
        self.dirty = 1

    def speed_up(self: Self) -> None:
        self._move.speed.speed_up_vertical()
