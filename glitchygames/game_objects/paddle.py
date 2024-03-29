#!/usr/bin/env python3
"""Paddle."""

from __future__ import annotations

import logging
from typing import Self

import pygame
from glitchygames.game_objects import load_sound
from glitchygames.movement import Horizontal, Vertical
from glitchygames.sprites import Sprite
from pygame import draw

log = logging.getLogger('game.paddle')
log.setLevel(logging.INFO)


class BasePaddle(Sprite):
    """Base Paddle class."""

    def __init__(
        self: Self,
        axis: Horizontal | Vertical,
        speed: int,
        name: str,
        color: tuple,
        x: int,
        y: int,
        width: int,
        height: int,
        groups: pygame.sprite.LayeredDirty | None = None,
        collision_sound: str | None = None,
    ) -> None:
        """Initialize the paddle.

        Args:
            axis (Horizontal | Vertical): The axis to move on.
            speed (int): The speed to move at.
            name (str): The name of the paddle.
            color (tuple): The color of the paddle.
            x (int): The x position of the paddle.
            y (int): The y position of the paddle.
            width (int): The width of the paddle.
            height (int): The height of the paddle.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.
            collision_sound (str | None): The sound to play on collision.

        Returns:
            None
        """
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
        """Move the paddle horizontally.

        Args:
            None

        Returns:
            None
        """
        self.rect.x += self._move.current_speed
        self.dirty = 1

    def move_vertical(self: Self) -> None:
        """Move the paddle vertically.

        Args:
            None

        Returns:
            None
        """
        self.rect.y += self._move.current_speed
        self.dirty = 1

    def is_at_bottom_of_screen(self: Self) -> bool:
        """Check if the paddle is at the bottom of the screen.

        Args:
            None

        Returns:
            bool: True if the paddle is at the bottom of the screen, False otherwise.
        """
        return self.rect.bottom + self._move.current_speed > self.screen_height

    def is_at_top_of_screen(self: Self) -> bool:
        """Check if the paddle is at the top of the screen.

        Args:
            None

        Returns:
            bool: True if the paddle is at the top of the screen, False otherwise.
        """
        return self.rect.top + self._move.current_speed < 0

    def is_at_left_of_screen(self: Self) -> bool:
        """Check if the paddle is at the left of the screen.

        Args:
            None

        Returns:
            bool: True if the paddle is at the left of the screen, False otherwise.
        """
        return self.rect.left + self._move.current_speed < self.screen.left

    def is_at_right_of_screen(self: Self) -> bool:
        """Check if the paddle is at the right of the screen.

        Args:
            None

        Returns:
            bool: True if the paddle is at the right of the screen, False otherwise.
        """
        return self.rect.right + self._move.current_speed > self.screen.right


class HorizontalPaddle(BasePaddle):
    """Horizontal Paddle."""

    def __init__(
        self: Self,
        name: str,
        size: tuple,
        position: tuple,
        color: tuple,
        speed: int,
        groups: pygame.sprite.LayeredDirty | None = None,
        collision_sound: str | None = None,
    ) -> None:
        """Initialize the horizontal paddle.

        Args:
            name (str): The name of the paddle.
            size (tuple): The size of the paddle.
            position (tuple): The position of the paddle.
            color (tuple): The color of the paddle.
            speed (int): The speed to move at.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.
            collision_sound (str | None): The sound to play on collision.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(
            Horizontal,
            speed,
            name,
            color,
            position[0],
            position[1],
            size[0],
            size[1],
            groups,
            collision_sound,
        )

    def update(self: Self) -> None:
        """Update the paddle.

        Args:
            None

        Returns:
            None
        """
        if self.is_at_left_of_screen():
            self.rect.x = 0
            self.stop()
        elif self.is_at_right_of_screen():
            self.rect.x = self.screen.right - self.rect.width
            self.stop()
        else:
            self.move_horizontal()

    def left(self: Self) -> None:
        """Move left.

        Args:
            None

        Returns:
            None
        """
        self._move.left()
        self.dirty = 1

    def right(self: Self) -> None:
        """Move right.

        Args:
            None

        Returns:
            None
        """
        self._move.right()
        self.dirty = 1

    def stop(self: Self) -> None:
        """Stop moving.

        Args:
            None

        Returns:
            None
        """
        self._move.stop()
        self.dirty = 1

    def speed_up(self: Self) -> None:
        """Speed up.

        Args:
            None

        Returns:
            None
        """
        self._move.speed.speed_up_horizontal()


class VerticalPaddle(BasePaddle):
    """Vertical Paddle."""

    def __init__(
        self: Self,
        name: str,
        size: tuple,
        position: tuple,
        color: tuple,
        speed: int,
        groups: pygame.sprite.LayeredDirty | None = None,
        collision_sound: str | None = None,
    ) -> None:
        """Initialize the vertical paddle.

        Args:
            name (str): The name of the paddle.
            size (tuple): The size of the paddle.
            position (tuple): The position of the paddle.
            color (tuple): The color of the paddle.
            speed (int): The speed to move at.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.
            collision_sound (str | None): The sound to play on collision.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(
            Vertical,
            speed,
            name,
            color,
            position[0],
            position[1],
            size[0],
            size[1],
            groups,
            collision_sound,
        )

    def update(self: Self) -> None:
        """Update the paddle.

        Args:
            None

        Returns:
            None
        """
        if self.is_at_top_of_screen():
            self.rect.y = 0
            self.stop()
        elif self.is_at_bottom_of_screen():
            self.rect.y = self.screen_height - self.rect.height
            self.stop()
        else:
            self.move_vertical()

    def up(self: Self) -> None:
        """Move up.

        Args:
            None

        Returns:
            None
        """
        self._move.up()
        self.dirty = 1

    def down(self: Self) -> None:
        """Move down.

        Args:
            None

        Returns:
            None
        """
        self._move.down()
        self.dirty = 1

    def stop(self: Self) -> None:
        """Stop moving.

        Args:
            None

        Returns:
            None
        """
        self._move.stop()
        self.dirty = 1

    def speed_up(self: Self) -> None:
        """Speed up.

        Args:
            None

        Returns:
            None
        """
        self._move.speed.speed_up_vertical()
