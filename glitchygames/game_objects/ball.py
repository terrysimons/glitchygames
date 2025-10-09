#!/usr/bin/env python3
"""Ball."""

from __future__ import annotations

import secrets
from typing import Self

import pygame
from glitchygames import game_objects
from glitchygames.color import WHITE
from glitchygames.movement import Speed
from glitchygames.sprites import Sprite


class BallSprite(Sprite):
    """Ball Sprite."""

    def __init__(
        self: Self,
        x: int = 0,
        y: int = 0,
        width: int = 20,
        height: int = 20,
        groups: pygame.sprite.LayeredDirty | None = None,
        collision_sound: str | None = None,
    ) -> None:
        """Initialize the ball sprite.

        Args:
            x (int): The x position of the ball.
            y (int): The y position of the ball.
            width (int): The width of the ball.
            height (int): The height of the ball.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.
            collision_sound (str | None): The sound to play on collision.

        Returns:
            None

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(x=x, y=y, width=width, height=height, groups=groups)
        self.use_gfxdraw = True
        self.image.convert()
        self.image.set_colorkey(0)
        self.direction = 0
        self.speed = Speed(2, 1)  # More reasonable default speed
        if collision_sound:
            self.snd = game_objects.load_sound(collision_sound)
        self.color = WHITE

        self.reset()

        # The ball always needs refreshing.
        # This saves us a set on dirty every update.
        self.dirty = 2

    @property
    def color(self: Self) -> tuple[int, int, int]:
        """Get the color of the ball.

        Args:
            None

        Returns:
            tuple[int, int, int]: The color of the ball.

        """
        return self._color

    @color.setter
    def color(self: Self, new_color: tuple) -> None:
        """Set the color of the ball.

        Args:
            new_color (tuple): The new color of the ball.

        Returns:
            None

        """
        self._color = new_color
        pygame.draw.circle(self.image, self._color, (self.width // 2, self.height // 2), 5, 0)

    def _do_bounce(self: Self) -> None:
        """Bounce the ball.

        Args:
            None

        Returns:
            None

        """
        if self.rect.y <= 0:
            if hasattr(self, "snd") and self.snd is not None:
                self.snd.play()
            self.rect.y = 0
            self.speed.y *= -1
        if self.rect.y + self.height >= self.screen_height:
            if hasattr(self, "snd") and self.snd is not None:
                self.snd.play()
            self.rect.y = self.screen_height - self.height
            self.speed.y *= -1

    def reset(self: Self) -> None:
        """Reset the ball.

        Args:
            None

        Returns:
            None

        """
        # Set position directly to rect, maintaining consistency
        self.rect.x = secrets.randbelow(700) + 50  # 50-749 range
        self.rect.y = secrets.randbelow(375) + 25  # 25-399 range

        # Direction of ball (in degrees)
        self.direction = secrets.randbelow(90) - 45  # -45 to 44 range

        # Flip a 'coin'
        if secrets.randbelow(2) == 0:
            # Reverse ball direction, let the other guy get it first
            self.direction += 180

        # Ensure direction is in 0-360 range
        self.direction %= 360

        # self.rally.reset()

    # This function will bounce the ball off a horizontal surface (not a vertical one)
    def bounce(self: Self, diff: int) -> None:
        """Bounce the ball.

        Args:
            diff (int): The difference.

        Returns:
            None

        """
        self.direction = (180 - self.direction) % 360
        self.direction -= diff

        # Speed the ball up
        self.speed *= 1.1

    def update(self: Self) -> None:
        """Update the ball.

        Args:
            None

        Returns:
            None

        """
        # Check for wall bounces before moving
        if self.rect.x <= 0:
            self.direction = (360 - self.direction) % 360
            self.rect.x = 1

        if self.rect.x > self.screen_width - self.width:
            self.direction = (360 - self.direction) % 360

        self.rect.y += self.speed.y
        self.rect.x += self.speed.x

        self._do_bounce()

        if self.rect.x > self.screen_width or self.rect.x < 0:
            self.reset()

        if self.rect.y > self.screen_height or self.rect.y < 0:
            self.reset()
