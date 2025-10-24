#!/usr/bin/env python3
"""Ball."""

from __future__ import annotations

import math
import secrets
import time
from typing import Self

import pygame
from glitchygames import game_objects
from glitchygames.color import WHITE
from glitchygames.movement import Speed
from glitchygames.sprites import Sprite


class BallSpawnMode:
    """Bitwise flags for ball spawn behavior."""
    NONE = 0
    
    # Spawn triggers
    ON_PADDLE_COLLISION = 1 << 0
    ON_WALL_BOUNCE = 1 << 1
    ON_BALL_COLLISION = 1 << 2
    ON_SCORE = 1 << 3
    
    # Spawn conditions
    SPEED_CHECK_ENABLED = 1 << 4  # Only spawn if ball speed is reasonable
    COOLDOWN_ENABLED = 1 << 5     # Respect cooldown between spawns
    RANDOM_POSITION = 1 << 6     # Spawn at random position vs fixed
    RANDOM_SPEED = 1 << 7        # Random initial speed vs fixed
    RANDOM_COLOR = 1 << 8        # Random color vs default
    
    # Spawn frequency controls
    FREQUENT = 1 << 9           # Short cooldown (0.5s)
    NORMAL = 1 << 10            # Normal cooldown (2.0s)
    RARE = 1 << 11              # Long cooldown (5.0s)
    
    # Convenience combinations
    PADDLE_ONLY = ON_PADDLE_COLLISION | SPEED_CHECK_ENABLED | COOLDOWN_ENABLED | RANDOM_POSITION | RANDOM_SPEED | RANDOM_COLOR | NORMAL
    WALL_ONLY = ON_WALL_BOUNCE | SPEED_CHECK_ENABLED | COOLDOWN_ENABLED | RANDOM_POSITION | RANDOM_SPEED | RANDOM_COLOR | NORMAL
    BALL_ONLY = ON_BALL_COLLISION | SPEED_CHECK_ENABLED | COOLDOWN_ENABLED | RANDOM_POSITION | RANDOM_SPEED | RANDOM_COLOR | NORMAL
    ALL_TRIGGERS = ON_PADDLE_COLLISION | ON_WALL_BOUNCE | ON_BALL_COLLISION | ON_SCORE
    FREQUENT_SPAWNING = ALL_TRIGGERS | SPEED_CHECK_ENABLED | COOLDOWN_ENABLED | RANDOM_POSITION | RANDOM_SPEED | RANDOM_COLOR | FREQUENT
    NO_SPAWNING = NONE


class SpeedUpMode:
    """Bitwise flags for ball speed-up modes with separate X and Y control."""
    NONE = 0
    
    # Continuous speed-up modes
    CONTINUOUS_LINEAR = 1 << 0
    CONTINUOUS_LOGARITHMIC_X = 1 << 1
    CONTINUOUS_LOGARITHMIC_Y = 1 << 2
    CONTINUOUS_EXPONENTIAL_X = 1 << 3
    CONTINUOUS_EXPONENTIAL_Y = 1 << 4
    
    # Bounce speed-up modes
    ON_BOUNCE_LINEAR = 1 << 5
    ON_BOUNCE_LOGARITHMIC_X = 1 << 6
    ON_BOUNCE_LOGARITHMIC_Y = 1 << 7
    ON_BOUNCE_EXPONENTIAL_X = 1 << 8
    ON_BOUNCE_EXPONENTIAL_Y = 1 << 9
    
    # Wall bounce speed-up modes
    ON_WALL_BOUNCE_LINEAR = 1 << 10
    ON_WALL_BOUNCE_LOGARITHMIC_X = 1 << 11
    ON_WALL_BOUNCE_LOGARITHMIC_Y = 1 << 12
    ON_WALL_BOUNCE_EXPONENTIAL_X = 1 << 13
    ON_WALL_BOUNCE_EXPONENTIAL_Y = 1 << 14
    
    # Combined modes
    ALL_LINEAR = CONTINUOUS_LINEAR | ON_BOUNCE_LINEAR | ON_WALL_BOUNCE_LINEAR
    ALL_LOGARITHMIC_X = CONTINUOUS_LOGARITHMIC_X | ON_BOUNCE_LOGARITHMIC_X | ON_WALL_BOUNCE_LOGARITHMIC_X
    ALL_LOGARITHMIC_Y = CONTINUOUS_LOGARITHMIC_Y | ON_BOUNCE_LOGARITHMIC_Y | ON_WALL_BOUNCE_LOGARITHMIC_Y
    ALL_EXPONENTIAL_X = CONTINUOUS_EXPONENTIAL_X | ON_BOUNCE_EXPONENTIAL_X | ON_WALL_BOUNCE_EXPONENTIAL_X
    ALL_EXPONENTIAL_Y = CONTINUOUS_EXPONENTIAL_Y | ON_BOUNCE_EXPONENTIAL_Y | ON_WALL_BOUNCE_EXPONENTIAL_Y
    
    # Convenience combinations
    BOUNCE_ONLY_LINEAR = ON_BOUNCE_LINEAR | ON_WALL_BOUNCE_LINEAR
    BOUNCE_ONLY_LOGARITHMIC_X = ON_BOUNCE_LOGARITHMIC_X | ON_WALL_BOUNCE_LOGARITHMIC_X
    BOUNCE_ONLY_LOGARITHMIC_Y = ON_BOUNCE_LOGARITHMIC_Y | ON_WALL_BOUNCE_LOGARITHMIC_Y
    BOUNCE_ONLY_EXPONENTIAL_X = ON_BOUNCE_EXPONENTIAL_X | ON_WALL_BOUNCE_EXPONENTIAL_X
    BOUNCE_ONLY_EXPONENTIAL_Y = ON_BOUNCE_EXPONENTIAL_Y | ON_WALL_BOUNCE_EXPONENTIAL_Y
    
    PADDLE_ONLY_LINEAR = ON_BOUNCE_LINEAR
    PADDLE_ONLY_LOGARITHMIC_X = ON_BOUNCE_LOGARITHMIC_X
    PADDLE_ONLY_LOGARITHMIC_Y = ON_BOUNCE_LOGARITHMIC_Y
    PADDLE_ONLY_EXPONENTIAL_X = ON_BOUNCE_EXPONENTIAL_X
    PADDLE_ONLY_EXPONENTIAL_Y = ON_BOUNCE_EXPONENTIAL_Y
    
    WALL_ONLY_LINEAR = ON_WALL_BOUNCE_LINEAR
    WALL_ONLY_LOGARITHMIC_X = ON_WALL_BOUNCE_LOGARITHMIC_X
    WALL_ONLY_LOGARITHMIC_Y = ON_WALL_BOUNCE_LOGARITHMIC_Y
    WALL_ONLY_EXPONENTIAL_X = ON_WALL_BOUNCE_EXPONENTIAL_X
    WALL_ONLY_EXPONENTIAL_Y = ON_WALL_BOUNCE_EXPONENTIAL_Y
    
    # Legacy aliases for backward compatibility - now use OR logic
    CONTINUOUS = CONTINUOUS_LOGARITHMIC_X | CONTINUOUS_LOGARITHMIC_Y
    ON_BOUNCE = ON_BOUNCE_LOGARITHMIC_X | ON_BOUNCE_LOGARITHMIC_Y
    ON_WALL_BOUNCE = ON_WALL_BOUNCE_LOGARITHMIC_X | ON_WALL_BOUNCE_LOGARITHMIC_Y
    ALL = ALL_LOGARITHMIC_X | ALL_LOGARITHMIC_Y
    BOUNCE_ONLY = BOUNCE_ONLY_LOGARITHMIC_X | BOUNCE_ONLY_LOGARITHMIC_Y
    WALL_ONLY = WALL_ONLY_LOGARITHMIC_X | WALL_ONLY_LOGARITHMIC_Y
    PADDLE_ONLY = PADDLE_ONLY_LOGARITHMIC_X | PADDLE_ONLY_LOGARITHMIC_Y


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
        bounce_top_bottom: bool = True,
        bounce_left_right: bool = False,
        speed_up_mode: int = SpeedUpMode.NONE,
        speed_up_multiplier: float = 1.1,
        speed_up_interval: float = 1.0,
    ) -> None:
        """Initialize the ball sprite.

        Args:
            x (int): The x position of the ball.
            y (int): The y position of the ball.
            width (int): The width of the ball.
            height (int): The height of the ball.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.
            collision_sound (str | None): The sound to play on collision.
            bounce_top_bottom (bool): Whether to bounce off top and bottom boundaries.
            bounce_left_right (bool): Whether to bounce off left and right boundaries.
            speed_up_mode (int): Bitwise flags for logarithmic speed-up behavior.
            speed_up_multiplier (float): Logarithmic multiplier for speed increases.
            speed_up_interval (float): Interval in seconds for continuous logarithmic speed-up.

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

        # Configure boundary bouncing behavior
        self.bounce_top_bottom = bounce_top_bottom
        self.bounce_left_right = bounce_left_right

        # Configure speed-up behavior
        self.speed_up_mode = speed_up_mode
        self.speed_up_multiplier = speed_up_multiplier
        self.speed_up_interval = speed_up_interval
        self._last_speed_up_time = 0.0

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
        # Debug log before bounce
        import logging
        log = logging.getLogger("game")
        log.debug(
            f"BALL BOUNCE CHECK: pos=({self.rect.x},{self.rect.y}) "
            f"speed=({self.speed.x:.3f},{self.speed.y:.3f}) "
            f"screen=({self.screen_width},{self.screen_height}) "
            f"bounce_top_bottom={self.bounce_top_bottom} bounce_left_right={self.bounce_left_right}"
        )
        
        # Top edge bounce
        if self.bounce_top_bottom and self.rect.y <= 0:
            if hasattr(self, "snd") and self.snd is not None:
                self.snd.play()
            log.debug(f"BALL BOUNCE: TOP EDGE - speed before=({self.speed.x:.3f},{self.speed.y:.3f})")
            self.rect.y = 0  # Position ball exactly at top boundary
            # Simple Y direction reversal
            self.speed.y = abs(self.speed.y)  # Ensure positive speed (downward)
            log.debug(f"BALL BOUNCE: TOP EDGE - speed after=({self.speed.x:.3f},{self.speed.y:.3f})")
            # Check for wall bounce speed-up
            self._check_bounce_speed_up("wall")

        # Bottom edge bounce
        if self.bounce_top_bottom and self.rect.y + self.height >= self.screen_height:
            if hasattr(self, "snd") and self.snd is not None:
                self.snd.play()
            log.debug(f"BALL BOUNCE: BOTTOM EDGE - speed before=({self.speed.x:.3f},{self.speed.y:.3f})")
            self.rect.y = self.screen_height - self.height  # Position ball exactly at bottom boundary
            # Simple Y direction reversal
            self.speed.y = -abs(self.speed.y)  # Ensure negative speed (upward)
            log.debug(f"BALL BOUNCE: BOTTOM EDGE - speed after=({self.speed.x:.3f},{self.speed.y:.3f})")
            # Check for wall bounce speed-up
            self._check_bounce_speed_up("wall")

        # Left edge bounce
        if self.bounce_left_right and self.rect.x <= 0:
            if hasattr(self, "snd") and self.snd is not None:
                self.snd.play()
            log.debug(f"BALL BOUNCE: LEFT EDGE - speed before=({self.speed.x:.3f},{self.speed.y:.3f})")
            self.rect.x = 1  # Small buffer to prevent sticking
            # Simple X direction reversal
            self.speed.x = abs(self.speed.x)  # Ensure positive speed (rightward)
            log.debug(f"BALL BOUNCE: LEFT EDGE - speed after=({self.speed.x:.3f},{self.speed.y:.3f})")
            # Check for wall bounce speed-up
            self._check_bounce_speed_up("wall")

        # Right edge bounce
        if self.bounce_left_right and self.rect.x + self.width >= self.screen_width:
            if hasattr(self, "snd") and self.snd is not None:
                self.snd.play()
            log.debug(f"BALL BOUNCE: RIGHT EDGE - speed before=({self.speed.x:.3f},{self.speed.y:.3f})")
            self.rect.x = self.screen_width - self.width - 1  # Small buffer to prevent sticking
            # Simple X direction reversal
            self.speed.x = -abs(self.speed.x)  # Ensure negative speed (leftward)
            log.debug(f"BALL BOUNCE: RIGHT EDGE - speed after=({self.speed.x:.3f},{self.speed.y:.3f})")
            # Check for wall bounce speed-up
            self._check_bounce_speed_up("wall")

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
        # Use a fixed, symmetric speed magnitude instead of calculating from current speed
        speed_magnitude = 250.0  # Fixed speed in pixels per second
        speed_x = speed_magnitude * math.cos(radians)
        speed_y = speed_magnitude * math.sin(radians)
        
        # Ensure minimum speed in both directions (avoid zero speeds)
        min_speed = 50.0  # Minimum 50 pixels per second in each direction
        if abs(speed_x) < min_speed:
            speed_x = min_speed if speed_x >= 0 else -min_speed
        if abs(speed_y) < min_speed:
            speed_y = min_speed if speed_y >= 0 else -min_speed
            
        self.speed.x = speed_x
        self.speed.y = speed_y

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

    def speed_up(self: Self, multiplier: float = None, speed_up_type: str = "linear") -> None:
        """Increase the ball's speed with linear, logarithmic, or exponential scaling.

        Args:
            multiplier (float): The speed multiplier to apply.
            speed_up_type (str): Type of speed-up ('linear', 'logarithmic_x', 'logarithmic_y', 'logarithmic_both', 'exponential_x', 'exponential_y', 'exponential_both').

        Returns:
            None

        """
        if multiplier is None:
            multiplier = self.speed_up_multiplier

        if speed_up_type == "linear":
            # Linear speed-up: preserve direction by scaling magnitude
            current_magnitude = math.sqrt(self.speed.x**2 + self.speed.y**2)
            if current_magnitude > 0:
                new_magnitude = current_magnitude * multiplier
                self.speed.x = (self.speed.x / current_magnitude) * new_magnitude
                self.speed.y = (self.speed.y / current_magnitude) * new_magnitude
        elif speed_up_type == "logarithmic_x":
            # Logarithmic X speed-up: only scale X component
            self.speed.x *= multiplier
        elif speed_up_type == "logarithmic_y":
            # Logarithmic Y speed-up: only scale Y component
            self.speed.y *= multiplier
        elif speed_up_type == "logarithmic_both":
            # Logarithmic both: scale both components (preserves direction)
            self.speed.x *= multiplier
            self.speed.y *= multiplier
        elif speed_up_type == "exponential_x":
            # Exponential X speed-up: exponential scaling of X component
            self.speed.x = self.speed.x * (multiplier ** abs(self.speed.x / 100.0)) if self.speed.x != 0 else 0
        elif speed_up_type == "exponential_y":
            # Exponential Y speed-up: exponential scaling of Y component
            self.speed.y = self.speed.y * (multiplier ** abs(self.speed.y / 100.0)) if self.speed.y != 0 else 0
        elif speed_up_type == "exponential_both":
            # Exponential both: exponential scaling of both components
            self.speed.x = self.speed.x * (multiplier ** abs(self.speed.x / 100.0)) if self.speed.x != 0 else 0
            self.speed.y = self.speed.y * (multiplier ** abs(self.speed.y / 100.0)) if self.speed.y != 0 else 0

    def _check_continuous_speed_up(self: Self, current_time: float) -> None:
        """Check if continuous speed-up should be applied.

        Args:
            current_time (float): Current time in seconds.

        Returns:
            None

        """
        if current_time - self._last_speed_up_time >= self.speed_up_interval:
            # Check for both X and Y exponential speed-up first (highest priority)
            if (self.speed_up_mode & SpeedUpMode.CONTINUOUS_EXPONENTIAL_X and 
                self.speed_up_mode & SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y):
                self.speed_up(speed_up_type="exponential_both")
                self._last_speed_up_time = current_time
            # Check for both X and Y logarithmic speed-up
            elif (self.speed_up_mode & SpeedUpMode.CONTINUOUS_LOGARITHMIC_X and 
                  self.speed_up_mode & SpeedUpMode.CONTINUOUS_LOGARITHMIC_Y):
                self.speed_up(speed_up_type="logarithmic_both")
                self._last_speed_up_time = current_time
            # Check for exponential X speed-up
            elif self.speed_up_mode & SpeedUpMode.CONTINUOUS_EXPONENTIAL_X:
                self.speed_up(speed_up_type="exponential_x")
                self._last_speed_up_time = current_time
            # Check for exponential Y speed-up
            elif self.speed_up_mode & SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y:
                self.speed_up(speed_up_type="exponential_y")
                self._last_speed_up_time = current_time
            # Check for logarithmic X speed-up
            elif self.speed_up_mode & SpeedUpMode.CONTINUOUS_LOGARITHMIC_X:
                self.speed_up(speed_up_type="logarithmic_x")
                self._last_speed_up_time = current_time
            # Check for logarithmic Y speed-up
            elif self.speed_up_mode & SpeedUpMode.CONTINUOUS_LOGARITHMIC_Y:
                self.speed_up(speed_up_type="logarithmic_y")
                self._last_speed_up_time = current_time
            # Check for linear speed-up
            elif self.speed_up_mode & SpeedUpMode.CONTINUOUS_LINEAR:
                self.speed_up(speed_up_type="linear")
                self._last_speed_up_time = current_time

    def _check_bounce_speed_up(self: Self, bounce_type: str) -> None:
        """Check if speed-up should be applied based on bounce type.

        Args:
            bounce_type (str): Type of bounce ('paddle' or 'wall').

        Returns:
            None

        """
        if bounce_type == "paddle":
            # Check for paddle bounce speed-up modes
            # Check for both X and Y exponential speed-up first (highest priority)
            if (self.speed_up_mode & SpeedUpMode.ON_BOUNCE_EXPONENTIAL_X and 
                self.speed_up_mode & SpeedUpMode.ON_BOUNCE_EXPONENTIAL_Y):
                self.speed_up(speed_up_type="exponential_both")
            # Check for both X and Y logarithmic speed-up
            elif (self.speed_up_mode & SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X and 
                  self.speed_up_mode & SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y):
                self.speed_up(speed_up_type="logarithmic_both")
            # Check for exponential X speed-up
            elif self.speed_up_mode & SpeedUpMode.ON_BOUNCE_EXPONENTIAL_X:
                self.speed_up(speed_up_type="exponential_x")
            # Check for exponential Y speed-up
            elif self.speed_up_mode & SpeedUpMode.ON_BOUNCE_EXPONENTIAL_Y:
                self.speed_up(speed_up_type="exponential_y")
            # Check for logarithmic X speed-up
            elif self.speed_up_mode & SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X:
                self.speed_up(speed_up_type="logarithmic_x")
            # Check for logarithmic Y speed-up
            elif self.speed_up_mode & SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y:
                self.speed_up(speed_up_type="logarithmic_y")
            # Check for linear speed-up
            elif self.speed_up_mode & SpeedUpMode.ON_BOUNCE_LINEAR:
                self.speed_up(speed_up_type="linear")
        elif bounce_type == "wall":
            # Check for wall bounce speed-up modes (check most specific first)
            # Check for both X and Y exponential speed-up first (highest priority)
            if (self.speed_up_mode & SpeedUpMode.ON_WALL_BOUNCE_EXPONENTIAL_X and 
                self.speed_up_mode & SpeedUpMode.ON_WALL_BOUNCE_EXPONENTIAL_Y):
                self.speed_up(speed_up_type="exponential_both")
            # Check for both X and Y logarithmic speed-up
            elif (self.speed_up_mode & SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X and 
                  self.speed_up_mode & SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y):
                self.speed_up(speed_up_type="logarithmic_both")
            # Check for exponential X speed-up
            elif self.speed_up_mode & SpeedUpMode.ON_WALL_BOUNCE_EXPONENTIAL_X:
                self.speed_up(speed_up_type="exponential_x")
            # Check for exponential Y speed-up
            elif self.speed_up_mode & SpeedUpMode.ON_WALL_BOUNCE_EXPONENTIAL_Y:
                self.speed_up(speed_up_type="exponential_y")
            # Check for logarithmic X speed-up
            elif self.speed_up_mode & SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X:
                self.speed_up(speed_up_type="logarithmic_x")
            # Check for logarithmic Y speed-up
            elif self.speed_up_mode & SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y:
                self.speed_up(speed_up_type="logarithmic_y")
            # Check for linear speed-up
            elif self.speed_up_mode & SpeedUpMode.ON_WALL_BOUNCE_LINEAR:
                self.speed_up(speed_up_type="linear")

    def on_paddle_bounce(self: Self) -> None:
        """Trigger paddle bounce logarithmic speed-up if enabled.

        Args:
            None

        Returns:
            None

        """
        self._check_bounce_speed_up("paddle")

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

        # Check for continuous speed-up
        current_time = time.time()
        
        # Debug log speed changes
        import logging
        log = logging.getLogger("game")
        old_speed_x, old_speed_y = self.speed.x, self.speed.y
        old_magnitude = math.sqrt(old_speed_x**2 + old_speed_y**2)
        
        self._check_continuous_speed_up(current_time)
        
        # Check if speed changed unexpectedly
        if abs(self.speed.x - old_speed_x) > 0.001 or abs(self.speed.y - old_speed_y) > 0.001:
            new_magnitude = math.sqrt(self.speed.x**2 + self.speed.y**2)
            log.debug(
                f"BALL SPEED CHANGE: old=({old_speed_x:.3f},{old_speed_y:.3f}) "
                f"new=({self.speed.x:.3f},{self.speed.y:.3f}) "
                f"magnitude_change={new_magnitude - old_magnitude:.3f}"
            )

        # Calculate movement
        move_x = self.speed.x * dt
        move_y = self.speed.y * dt

        # Debug log movement calculation
        import logging
        log = logging.getLogger("game")
        
        # Check for weird upward curving behavior
        if abs(move_y) > 0.1:  # Only log significant Y movement
            log.debug(
                f"BALL MOVE: speed=({self.speed.x:.3f},{self.speed.y:.3f}) dt={dt:.6f} "
                f"move=({move_x:.3f},{move_y:.3f}) pos=({self.rect.x},{self.rect.y}) "
                f"speed_magnitude={math.sqrt(self.speed.x**2 + self.speed.y**2):.3f}"
            )

        # Use proper rounding to avoid precision loss from integer truncation
        old_x, old_y = self.rect.x, self.rect.y
        self.rect.x += round(move_x)
        self.rect.y += round(move_y)
        
        # Debug log final position and check for unexpected movement
        delta_x = self.rect.x - old_x
        delta_y = self.rect.y - old_y
        
        # Check for weird curving behavior
        if abs(delta_y) > 0.1:  # Only log significant Y movement
            log.debug(
                f"BALL MOVE: final_pos=({self.rect.x},{self.rect.y}) "
                f"delta=({delta_x},{delta_y}) "
                f"expected_move=({round(move_x)},{round(move_y)}) "
                f"actual_move=({delta_x},{delta_y})"
            )
            
            # Check if movement matches expectation
            if delta_x != round(move_x) or delta_y != round(move_y):
                log.debug(
                    f"BALL MOVE WARNING: Movement mismatch! "
                    f"Expected=({round(move_x)},{round(move_y)}) "
                    f"Actual=({delta_x},{delta_y})"
                )

        # Ensure the ball is marked as dirty for redrawing
        self.dirty = 1

        # Check for paddle collisions and prevent clipping
        self._check_paddle_collisions()

        self._do_bounce()

        # Only kill ball if it goes off screen and left/right bouncing is disabled
        if not self.bounce_left_right and (
            self.rect.x > self.screen_width or self.rect.x < -self.width
        ):
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

    def _do_bounce(self: Self) -> None:
        """Enhanced ball boundary physics with improved collision response.

        Args:
            None

        Returns:
            None

        """
        import logging
        log = logging.getLogger("game")
        log.debug(
            f"BALL BOUNCE CHECK: pos=({self.rect.x},{self.rect.y}) "
            f"speed=({self.speed.x:.3f},{self.speed.y:.3f}) "
            f"screen=({self.screen_width},{self.screen_height}) "
            f"bounce_top_bottom={self.bounce_top_bottom} bounce_left_right={self.bounce_left_right}"
        )
        
        # Enhanced boundary checking with proper physics
        self._handle_boundary_collisions(log)

    def _handle_boundary_collisions(self: Self, log) -> None:
        """Handle boundary collisions with enhanced physics.
        
        Args:
            log: Logger instance for debug output
            
        Returns:
            None
        """
        # Track if any collision occurred for corner detection
        collision_occurred = False
        
        # Top edge bounce: include boundary contact (<= 0)
        if self.bounce_top_bottom and self.rect.y <= 0:
            collision_occurred = True
            self._handle_top_collision(log)
            
        # Bottom edge bounce: include boundary contact (>= screen_height)
        if self.bounce_top_bottom and self.rect.y + self.height >= self.screen_height:
            collision_occurred = True
            self._handle_bottom_collision(log)
            
        # Left edge bounce: include boundary contact (<= 0)
        if self.bounce_left_right and self.rect.x <= 0:
            collision_occurred = True
            self._handle_left_collision(log)
            
        # Right edge bounce: include boundary contact (>= screen_width)
        if self.bounce_left_right and self.rect.x + self.width >= self.screen_width:
            collision_occurred = True
            self._handle_right_collision(log)
            
        # Handle corner collisions (when ball hits multiple boundaries simultaneously)
        if collision_occurred:
            self._handle_corner_collision(log)

    def _handle_top_collision(self: Self, log) -> None:
        """Handle collision with top boundary with realistic physics.
        
        Args:
            log: Logger instance for debug output
            
        Returns:
            None
        """
        if hasattr(self, "snd") and self.snd is not None:
            self.snd.play()
            
        # Enhanced positioning to prevent clipping (historic +1 padding expected by tests)
        self.rect.y = 1  # Place just inside the boundary
        
        # Realistic bounce physics - preserve speed magnitude and reflect angle
        speed_magnitude = math.sqrt(self.speed.x**2 + self.speed.y**2)
        if speed_magnitude > 0:
            # Calculate reflection angle (perfect elastic collision)
            # For top boundary: reflect Y component, preserve X component
            self.speed.y = abs(self.speed.y)  # Ensure positive speed (downward)
            # X component remains unchanged for realistic bounce
            
            # Add visual feedback for collision
            self._add_collision_visual_feedback("top", log)
        
        log.debug(f"BALL BOUNCE: TOP EDGE - speed before=({self.speed.x:.3f},{self.speed.y:.3f})")
        log.debug(f"BALL BOUNCE: TOP EDGE - speed after=({self.speed.x:.3f},{self.speed.y:.3f})")
        self._check_bounce_speed_up("wall")

    def _handle_bottom_collision(self: Self, log) -> None:
        """Handle collision with bottom boundary with realistic physics.
        
        Args:
            log: Logger instance for debug output
            
        Returns:
            None
        """
        if hasattr(self, "snd") and self.snd is not None:
            self.snd.play()
            
        # Enhanced positioning to prevent clipping (historic -1 padding expected by tests)
        self.rect.y = self.screen_height - self.height - 1
        
        # Realistic bounce physics - preserve speed magnitude and reflect angle
        speed_magnitude = math.sqrt(self.speed.x**2 + self.speed.y**2)
        if speed_magnitude > 0:
            # Calculate reflection angle (perfect elastic collision)
            # For bottom boundary: reflect Y component, preserve X component
            self.speed.y = -abs(self.speed.y)  # Ensure negative speed (upward)
            # X component remains unchanged for realistic bounce
            
            # Add visual feedback for collision
            self._add_collision_visual_feedback("bottom", log)
        
        log.debug(f"BALL BOUNCE: BOTTOM EDGE - speed before=({self.speed.x:.3f},{self.speed.y:.3f})")
        log.debug(f"BALL BOUNCE: BOTTOM EDGE - speed after=({self.speed.x:.3f},{self.speed.y:.3f})")
        self._check_bounce_speed_up("wall")

    def _handle_left_collision(self: Self, log) -> None:
        """Handle collision with left boundary with realistic physics.
        
        Args:
            log: Logger instance for debug output
            
        Returns:
            None
        """
        if hasattr(self, "snd") and self.snd is not None:
            self.snd.play()
            
        # Enhanced positioning to prevent clipping (keep historic +1 padding)
        self.rect.x = 1  # Ensure ball is just inside left boundary
        
        # Realistic bounce physics - preserve speed magnitude and reflect angle
        speed_magnitude = math.sqrt(self.speed.x**2 + self.speed.y**2)
        if speed_magnitude > 0:
            # Calculate reflection angle (perfect elastic collision)
            # For left boundary: reflect X component, preserve Y component
            self.speed.x = abs(self.speed.x)  # Ensure positive speed (rightward)
            # Y component remains unchanged for realistic bounce
            
            # Add visual feedback for collision
            self._add_collision_visual_feedback("left", log)
        
        log.debug(f"BALL BOUNCE: LEFT EDGE - speed before=({self.speed.x:.3f},{self.speed.y:.3f})")
        log.debug(f"BALL BOUNCE: LEFT EDGE - speed after=({self.speed.x:.3f},{self.speed.y:.3f})")
        self._check_bounce_speed_up("wall")

    def _handle_right_collision(self: Self, log) -> None:
        """Handle collision with right boundary with realistic physics.
        
        Args:
            log: Logger instance for debug output
            
        Returns:
            None
        """
        if hasattr(self, "snd") and self.snd is not None:
            self.snd.play()
            
        # Enhanced positioning to prevent clipping (keep historic -1 padding)
        self.rect.x = self.screen_width - self.width - 1
        
        # Realistic bounce physics - preserve speed magnitude and reflect angle
        speed_magnitude = math.sqrt(self.speed.x**2 + self.speed.y**2)
        if speed_magnitude > 0:
            # Calculate reflection angle (perfect elastic collision)
            # For right boundary: reflect X component, preserve Y component
            self.speed.x = -abs(self.speed.x)  # Ensure negative speed (leftward)
            # Y component remains unchanged for realistic bounce
            
            # Add visual feedback for collision
            self._add_collision_visual_feedback("right", log)
        
        log.debug(f"BALL BOUNCE: RIGHT EDGE - speed before=({self.speed.x:.3f},{self.speed.y:.3f})")
        log.debug(f"BALL BOUNCE: RIGHT EDGE - speed after=({self.speed.x:.3f},{self.speed.y:.3f})")
        self._check_bounce_speed_up("wall")

    def _handle_corner_collision(self: Self, log) -> None:
        """Handle corner collisions with enhanced physics and visual feedback.
        
        Args:
            log: Logger instance for debug output
            
        Returns:
            None
        """
        # Check if ball is in a corner position - include boundary contact
        in_top_left = self.rect.y <= 0 and self.rect.x <= 0
        in_top_right = self.rect.y <= 0 and self.rect.x + self.width >= self.screen_width
        in_bottom_left = self.rect.y + self.height >= self.screen_height and self.rect.x <= 0
        in_bottom_right = (self.rect.y + self.height >= self.screen_height and 
                          self.rect.x + self.width >= self.screen_width)
        
        if in_top_left or in_top_right or in_bottom_left or in_bottom_right:
            log.debug(f"BALL CORNER COLLISION: {in_top_left=} {in_top_right=} {in_bottom_left=} {in_bottom_right=}")
            
            # Enhanced corner physics - both X and Y components are reflected
            speed_magnitude = math.sqrt(self.speed.x**2 + self.speed.y**2)
            if speed_magnitude > 0:
                # For corner collisions, both components are reflected
                if in_top_left or in_bottom_right:
                    # Diagonal reflection: both X and Y are reversed
                    self.speed.x = abs(self.speed.x) if self.speed.x < 0 else -abs(self.speed.x)
                    self.speed.y = abs(self.speed.y) if self.speed.y < 0 else -abs(self.speed.y)
                elif in_top_right or in_bottom_left:
                    # Diagonal reflection: both X and Y are reversed
                    self.speed.x = -abs(self.speed.x) if self.speed.x > 0 else abs(self.speed.x)
                    self.speed.y = abs(self.speed.y) if self.speed.y < 0 else -abs(self.speed.y)
                
                # Add special visual feedback for corner collisions
                self._add_collision_visual_feedback("corner", log)
            
            # For corner collisions, ensure ball is properly positioned
            if in_top_left:
                self.rect.x = 1
                self.rect.y = 1
            elif in_top_right:
                self.rect.x = self.screen_width - self.width - 1
                self.rect.y = 1
            elif in_bottom_left:
                self.rect.x = 1
                self.rect.y = self.screen_height - self.height - 1
            elif in_bottom_right:
                self.rect.x = self.screen_width - self.width - 1
                self.rect.y = self.screen_height - self.height - 1

    def _add_collision_visual_feedback(self: Self, collision_type: str, log) -> None:
        """Add visual feedback for collision points and bounce directions.
        
        Args:
            collision_type: Type of collision ("top", "bottom", "left", "right", "corner")
            log: Logger instance for debug output
            
        Returns:
            None
        """
        # Visual feedback implementation
        # This could include:
        # - Particle effects at collision point
        # - Screen shake
        # - Color changes
        # - Trail effects showing bounce direction
        
        # For now, we'll add debug logging and prepare for future visual effects
        log.debug(f"BALL COLLISION VISUAL FEEDBACK: {collision_type} at ({self.rect.x}, {self.rect.y})")
        
        # Future implementation could include:
        # - Particle system for collision sparks
        # - Screen shake effect
        # - Ball color change on collision
        # - Trail effect showing bounce direction
        # - Sound effect variations based on collision type
        
        # Mark ball as needing visual update
        self.dirty = 2  # Force full redraw for visual effects

    def _check_paddle_collisions(self: Self) -> None:
        """Check for paddle collisions and prevent ball clipping through paddles.
        
        Args:
            None
            
        Returns:
            None
        """
        # Get all paddle sprites from the same groups as this ball
        paddle_sprites = []
        for group in self.groups():
            for sprite in group:
                # Check if this is a paddle (has snd attribute or is a paddle type)
                if (hasattr(sprite, 'snd') or 
                    sprite.__class__.__name__.lower().find('paddle') != -1) and sprite != self:
                    paddle_sprites.append(sprite)
        
        # Check collision with each paddle
        for paddle in paddle_sprites:
            if self.rect.colliderect(paddle.rect):
                # Ball is overlapping with paddle - adjust position to prevent clipping
                self._adjust_position_for_paddle_collision(paddle)

    def _adjust_position_for_paddle_collision(self: Self, paddle) -> None:
        """Adjust ball position to prevent clipping through paddle and make it bounce.
        
        Args:
            paddle: The paddle sprite that the ball is colliding with
            
        Returns:
            None
        """
        # Determine which side of the paddle the ball is on
        ball_center_x = self.rect.centerx
        paddle_center_x = paddle.rect.centerx
        
        if ball_center_x < paddle_center_x:
            # Ball is on the left side of paddle - position ball to the left of paddle
            self.rect.right = paddle.rect.left
            # Bounce off left side of paddle (reverse X direction)
            self.speed.x = -abs(self.speed.x)
        else:
            # Ball is on the right side of paddle - position ball to the right of paddle  
            self.rect.left = paddle.rect.right
            # Bounce off right side of paddle (reverse X direction)
            self.speed.x = abs(self.speed.x)
        
        # Play collision sound if paddle has one
        if hasattr(paddle, 'snd') and paddle.snd:
            paddle.snd.play()
        
        # Check for paddle bounce speed-up (this triggers ball spawn)
        self._check_bounce_speed_up("paddle")
        
        # Cap speed after paddle collision to prevent runaway physics
        max_speed = 500.0  # Maximum speed in pixels per second
        speed_magnitude = math.sqrt(self.speed.x**2 + self.speed.y**2)
        if speed_magnitude > max_speed:
            # Scale down the speed while preserving direction
            scale_factor = max_speed / speed_magnitude
            self.speed.x *= scale_factor
            self.speed.y *= scale_factor
        
        # Notify the game that a paddle collision occurred (for ball spawn)
        if hasattr(self, 'on_paddle_collision'):
            self.on_paddle_collision(self)
        
        # Mark ball as dirty for redraw
        self.dirty = 2
