#!/usr/bin/env python3
"""Ball."""

from __future__ import annotations

import math
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
        self.speed = Speed(250.0, 125.0)  # 250 pixels/second horizontal, 125 pixels/second vertical
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
        # Top edge bounce
        if self.rect.y <= 0:
            if hasattr(self, "snd") and self.snd is not None:
                self.snd.play()
            self.rect.y = 1  # Small buffer to prevent sticking
            self.speed.y = abs(self.speed.y)  # Ensure positive speed (downward)

        # Bottom edge bounce
        if self.rect.y + self.height >= self.screen_height:
            if hasattr(self, "snd") and self.snd is not None:
                self.snd.play()
            self.rect.y = self.screen_height - self.height - 1  # Small buffer to prevent sticking
            self.speed.y = -abs(self.speed.y)  # Ensure negative speed (upward)

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

        # Direction of ball (in degrees) - avoid pure vertical movement
        # Use ranges that ensure horizontal movement
        if secrets.randbelow(2) == 0:
            # Left side: aim right (0-90 or 270-360 degrees)
            self.direction = secrets.randbelow(90) + 270  # 270-359 degrees
        else:
            # Right side: aim left (90-270 degrees)
            self.direction = secrets.randbelow(180) + 90  # 90-269 degrees

        # Convert direction to speed components
        radians = math.radians(self.direction)
        speed_magnitude = math.sqrt(
            self.speed.x**2 + self.speed.y**2
        )  # Preserve original speed magnitude
        self.speed.x = speed_magnitude * math.cos(radians)
        self.speed.y = speed_magnitude * math.sin(radians)

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

    def speed_up(self: Self, multiplier: float = 1.1) -> None:
        """Increase the ball's speed logarithmically.

        Args:
            multiplier (float): The base speed multiplier to apply.

        Returns:
            None

        """
        # Calculate current speed magnitude
        current_speed = math.sqrt(self.speed.x**2 + self.speed.y**2)

        # Logarithmic scaling: faster balls get smaller increases
        # Base multiplier decreases as speed increases (using new base speed of 1)
        log_multiplier = multiplier * (1.0 - math.log(current_speed / 1.0) * 0.1)

        # Ensure minimum multiplier of 1.05 (5% minimum increase)
        log_multiplier = max(log_multiplier, 1.05)

        self.speed.x *= log_multiplier
        self.speed.y *= log_multiplier

    def dt_tick(self: Self, dt: float) -> None:
        """Update the ball with delta time.

        Args:
            dt (float): The delta time.

        Returns:
            None

        """
        # Use centralized performance manager for adaptive clamping
        from glitchygames.performance import performance_manager
        dt = performance_manager.get_adaptive_dt(dt)
        
        # Calculate movement
        move_x = self.speed.x * dt
        move_y = self.speed.y * dt
        
        self.rect.y += move_y
        self.rect.x += move_x
        
        # Ensure the ball is marked as dirty for redrawing
        self.dirty = 1

        self._do_bounce()

        # Only reset if ball goes completely off screen (after bounce handling)
        if self.rect.x > self.screen_width or self.rect.x < -self.width:
            # Mark ball for deletion instead of resetting
            self.kill()

        # Don't reset for vertical boundaries - let bounce handle them
        # if self.rect.y > self.screen_height or self.rect.y < 0:
        #     self.reset()

    def update(self: Self) -> None:
        """Update the ball.

        Args:
            None

        Returns:
            None

        """
        # Movement is now handled in dt_tick() for frame-rate independence
        # This method is kept for compatibility but no longer moves the ball
        pass
