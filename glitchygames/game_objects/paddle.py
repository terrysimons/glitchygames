#!/usr/bin/env python3
"""Paddle."""

from __future__ import annotations

import logging
from typing import Self, override

import pygame
from pygame import draw

from glitchygames.movement import Horizontal, Vertical
from glitchygames.movement.speed import Speed
from glitchygames.sprites import Sprite

from .sounds import load_sound

log = logging.getLogger('game.paddle')
log.setLevel(logging.INFO)


class BasePaddle(Sprite):
    """Base Paddle class."""

    def __init__(
        self: Self,
        axis: type[Horizontal | Vertical],
        speed: int,
        name: str,
        color: tuple[int, int, int],
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
        collision_sound: str | None = None,
    ) -> None:
        """Initialize the paddle.

        Args:
            axis (type[Horizontal] | type[Vertical]): The axis to move on.
            speed (int): The speed to move at.
            name (str): The name of the paddle.
            color (tuple[int, int, int]): The color of the paddle.
            x (int): The x position of the paddle.
            y (int): The y position of the paddle.
            width (int): The width of the paddle.
            height (int): The height of the paddle.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.
            collision_sound (str | None): The sound to play on collision.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()  # type: ignore[type-arg]

        super().__init__(name=name, x=x, y=y, width=width, height=height, groups=groups)  # type: ignore[arg-type]

        self.use_gfxdraw = True
        self.moving = False

        self.image.convert()
        draw.rect(self.image, color, (0, 0, self.width, self.height))
        if collision_sound:
            self.snd = load_sound(collision_sound)
        # Create Speed object based on axis type
        speed_obj = Speed(speed, 0) if axis is Horizontal else Speed(0, speed)
        self._move: Horizontal | Vertical = axis(speed_obj)
        self.dirty = 1

    def move_horizontal(self: Self) -> None:
        """Move the paddle horizontally.

        Args:
            None

        """
        self.rect.x += self._move.current_speed
        self.dirty = 1

    def move_vertical(self: Self) -> None:
        """Move the paddle vertically.

        Args:
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
        return self.rect.bottom >= self.screen_height

    def is_at_top_of_screen(self: Self) -> bool:
        """Check if the paddle is at the top of the screen.

        Args:
            None

        Returns:
            bool: True if the paddle is at the top of the screen, False otherwise.

        """
        return self.rect.top <= 0

    def is_at_left_of_screen(self: Self) -> bool:
        """Check if the paddle is at the left of the screen.

        Args:
            None

        Returns:
            bool: True if the paddle is at the left of the screen, False otherwise.

        """
        assert self.screen is not None

        screen_rect = self.screen.get_rect()
        return self.rect.left + self._move.current_speed < screen_rect.left

    def is_at_right_of_screen(self: Self) -> bool:
        """Check if the paddle is at the right of the screen.

        Args:
            None

        Returns:
            bool: True if the paddle is at the right of the screen, False otherwise.

        """
        assert self.screen is not None

        screen_rect = self.screen.get_rect()
        return self.rect.right + self._move.current_speed > screen_rect.right


class HorizontalPaddle(BasePaddle):
    """Horizontal Paddle."""

    def __init__(
        self: Self,
        name: str,
        size: tuple[int, int],
        position: tuple[int, int],
        color: tuple[int, int, int],
        speed: int,
        *,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
        collision_sound: str | None = None,
    ) -> None:
        """Initialize the horizontal paddle.

        Args:
            name (str): The name of the paddle.
            size (tuple[int, int]): The size of the paddle.
            position (tuple[int, int]): The position of the paddle.
            color (tuple[int, int, int]): The color of the paddle.
            speed (int): The speed to move at.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.
            collision_sound (str | None): The sound to play on collision.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()  # type: ignore[type-arg]
        super().__init__(  # type: ignore[arg-type]
            Horizontal,
            speed,
            name,
            color,
            x=position[0],
            y=position[1],
            width=size[0],
            height=size[1],
            groups=groups,
            collision_sound=collision_sound,
        )

    @override
    def update(self: Self) -> None:
        """Update the paddle.

        Args:
            None

        """
        assert self.screen is not None
        if self.is_at_left_of_screen():
            self.rect.x = 0
            self.stop()
        elif self.is_at_right_of_screen():
            self.rect.x = self.screen.get_rect().right - self.rect.width
            self.stop()
        else:
            self.move_horizontal()

    def left(self: Self) -> None:
        """Move left.

        Args:
            None

        """
        assert isinstance(self._move, Horizontal)
        self._move.left()
        self.dirty = 1

    def right(self: Self) -> None:
        """Move right.

        Args:
            None

        """
        assert isinstance(self._move, Horizontal)
        self._move.right()
        self.dirty = 1

    def stop(self: Self) -> None:
        """Stop moving.

        Args:
            None

        """
        self._move.stop()
        self.dirty = 1

    def speed_up(self: Self) -> None:
        """Speed up.

        Args:
            None

        """
        self._move.speed.speed_up_horizontal()
        self._move.current_speed = self._move.speed.x

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Update the horizontal paddle with delta time.

        Args:
            dt (float): The delta time.

        """
        # Use the movement class's get_movement_with_dt method for frame-rate independent movement
        movement = self._move.get_movement_with_dt(dt)

        # Use proper rounding to avoid precision loss from integer truncation

        self.rect.x += round(movement)

        self.dirty = 1


class VerticalPaddle(BasePaddle):
    """Vertical Paddle."""

    def __init__(
        self: Self,
        name: str,
        size: tuple[int, int],
        position: tuple[int, int],
        color: tuple[int, int, int],
        speed: int,
        *,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
        collision_sound: str | None = None,
    ) -> None:
        """Initialize the vertical paddle.

        Args:
            name (str): The name of the paddle.
            size (tuple[int, int]): The size of the paddle.
            position (tuple[int, int]): The position of the paddle.
            color (tuple[int, int, int]): The color of the paddle.
            speed (int): The speed to move at.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.
            collision_sound (str | None): The sound to play on collision.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()  # type: ignore[type-arg]

        super().__init__(  # type: ignore[arg-type]
            Vertical,
            speed,
            name,
            color,
            x=position[0],
            y=position[1],
            width=size[0],
            height=size[1],
            groups=groups,
            collision_sound=collision_sound,
        )

    @override
    def update(self: Self) -> None:
        """Update the paddle.

        Args:
            None

        """
        # Movement is now handled in dt_tick() for frame-rate independence
        # Constrain position at boundaries AND stop movement to prevent bouncing
        if self.rect.y < 0:
            self.rect.y = 0
            self.stop()  # Stop movement to prevent bouncing
        elif self.rect.y + self.rect.height > self.screen_height:
            self.rect.y = self.screen_height - self.rect.height
            self.stop()  # Stop movement to prevent bouncing

    def up(self: Self) -> None:
        """Move up.

        Args:
            None

        """
        assert isinstance(self._move, Vertical)
        self._move.up()
        self.dirty = 1

    def down(self: Self) -> None:
        """Move down.

        Args:
            None

        """
        assert isinstance(self._move, Vertical)
        self._move.down()
        self.dirty = 1

    def stop(self: Self) -> None:
        """Stop moving.

        Args:
            None

        """
        self._move.stop()
        self.dirty = 1

    def speed_up(self: Self) -> None:
        """Speed up.

        Args:
            None

        """
        self._move.speed.speed_up_vertical()
        self._move.current_speed = self._move.speed.y

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Update the vertical paddle with delta time.

        Args:
            dt (float): The delta time.

        """
        # Use centralized performance manager for adaptive clamping
        from glitchygames.performance import performance_manager

        dt = performance_manager.get_adaptive_dt(dt)

        # Use the movement class's get_movement_with_dt method for frame-rate independent movement
        movement = self._move.get_movement_with_dt(dt)

        # Use proper rounding to avoid precision loss from integer truncation

        self.rect.y += round(movement)

        self.dirty = 1
