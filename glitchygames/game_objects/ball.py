#!/usr/bin/env python3
"""Ball."""

from __future__ import annotations

import logging
import math
import secrets
import time
from typing import TYPE_CHECKING, Self, override

if TYPE_CHECKING:
    from collections.abc import Callable

import pygame

from glitchygames import game_objects
from glitchygames.color import WHITE
from glitchygames.movement import Speed
from glitchygames.sprites import Sprite

log: logging.Logger = logging.getLogger('game.objects.ball')

# Threshold below which speed changes are considered noise
SPEED_CHANGE_NOISE_FLOOR = 0.001

# Minimum Y movement to be considered significant for logging
SIGNIFICANT_MOVEMENT_THRESHOLD = 0.1


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
    COOLDOWN_ENABLED = 1 << 5  # Respect cooldown between spawns
    RANDOM_POSITION = 1 << 6  # Spawn at random position vs fixed
    RANDOM_SPEED = 1 << 7  # Random initial speed vs fixed
    RANDOM_COLOR = 1 << 8  # Random color vs default

    # Spawn frequency controls
    FREQUENT = 1 << 9  # Short cooldown (0.5s)
    NORMAL = 1 << 10  # Normal cooldown (2.0s)
    RARE = 1 << 11  # Long cooldown (5.0s)

    # Convenience combinations
    PADDLE_ONLY = (
        ON_PADDLE_COLLISION
        | SPEED_CHECK_ENABLED
        | COOLDOWN_ENABLED
        | RANDOM_POSITION
        | RANDOM_SPEED
        | RANDOM_COLOR
        | NORMAL
    )
    WALL_ONLY = (
        ON_WALL_BOUNCE
        | SPEED_CHECK_ENABLED
        | COOLDOWN_ENABLED
        | RANDOM_POSITION
        | RANDOM_SPEED
        | RANDOM_COLOR
        | NORMAL
    )
    BALL_ONLY = (
        ON_BALL_COLLISION
        | SPEED_CHECK_ENABLED
        | COOLDOWN_ENABLED
        | RANDOM_POSITION
        | RANDOM_SPEED
        | RANDOM_COLOR
        | NORMAL
    )
    ALL_TRIGGERS = ON_PADDLE_COLLISION | ON_WALL_BOUNCE | ON_BALL_COLLISION | ON_SCORE
    FREQUENT_SPAWNING = (
        ALL_TRIGGERS
        | SPEED_CHECK_ENABLED
        | COOLDOWN_ENABLED
        | RANDOM_POSITION
        | RANDOM_SPEED
        | RANDOM_COLOR
        | FREQUENT
    )
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
    ALL_LOGARITHMIC_X = (
        CONTINUOUS_LOGARITHMIC_X | ON_BOUNCE_LOGARITHMIC_X | ON_WALL_BOUNCE_LOGARITHMIC_X
    )
    ALL_LOGARITHMIC_Y = (
        CONTINUOUS_LOGARITHMIC_Y | ON_BOUNCE_LOGARITHMIC_Y | ON_WALL_BOUNCE_LOGARITHMIC_Y
    )
    ALL_EXPONENTIAL_X = (
        CONTINUOUS_EXPONENTIAL_X | ON_BOUNCE_EXPONENTIAL_X | ON_WALL_BOUNCE_EXPONENTIAL_X
    )
    ALL_EXPONENTIAL_Y = (
        CONTINUOUS_EXPONENTIAL_Y | ON_BOUNCE_EXPONENTIAL_Y | ON_WALL_BOUNCE_EXPONENTIAL_Y
    )

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
        *,
        x: int = 0,
        y: int = 0,
        width: int = 20,
        height: int = 20,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
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

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()  # type: ignore[type-arg]

        super().__init__(x=x, y=y, width=width, height=height, groups=groups)  # type: ignore[arg-type]
        self.use_gfxdraw = True
        self.image.convert()
        self.image.set_colorkey(0)
        self.direction = 0
        self.speed = Speed(250.0, 125.0)  # 250 pixels/second horizontal, 125 pixels/second vertical

        # Sub-pixel position tracking (floats for accurate physics,
        # rect uses rounded integers for rendering only)
        self.world_x: float = float(x)
        self.world_y: float = float(y)
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
        self._last_speed_up_time = time.time()  # Initialize to current time

        # Collision tracking (set by callers like PaddleSlap)
        self.collision_cooldowns: dict[str, float] = {}
        self.on_paddle_collision: Callable[[BallSprite], None] | None = None

        # Debug trajectory tracking (used for trajectory analysis)
        self._debug_positions: list[tuple[float, float, float, float]] = []

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
    def color(self: Self, new_color: tuple[int, int, int]) -> None:
        """Set the color of the ball.

        Args:
            new_color (tuple): The new color of the ball.

        """
        self._color = new_color
        pygame.draw.circle(self.image, self._color, (self.width // 2, self.height // 2), 5, 0)

    def reset(self: Self) -> None:
        """Reset the ball.

        Args:
            None

        """
        # Set sub-pixel position, then sync to rect for rendering
        self.world_x = float(secrets.randbelow(700) + 50)  # 50-749 range
        self.world_y = float(secrets.randbelow(375) + 25)  # 25-399 range
        self.rect.x = round(self.world_x)
        self.rect.y = round(self.world_y)

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

    # This function will bounce the ball off a horizontal surface (not a vertical one)
    def bounce(self: Self, diff: int) -> None:
        """Bounce the ball.

        Args:
            diff (int): The difference.

        """
        self.direction = (180 - self.direction) % 360
        self.direction -= diff

        # Speed the ball up
        self.speed *= 1.1

    def speed_up(
        self: Self,
        multiplier: float | None = None,
        speed_up_type: str = 'linear',
    ) -> None:
        """Increase the ball's speed with linear, logarithmic, or exponential scaling.

        Args:
            multiplier (float): The speed multiplier to apply.
            speed_up_type (str): Type of speed-up ('linear',
                'logarithmic_x', 'logarithmic_y',
                'logarithmic_both', 'exponential_x',
                'exponential_y', 'exponential_both').

        """
        if multiplier is None:
            multiplier = self.speed_up_multiplier

        if speed_up_type in {'linear', 'logarithmic_both'}:
            # Scale both components equally -- preserves trajectory angle
            self.speed.x *= multiplier
            self.speed.y *= multiplier
        elif speed_up_type == 'logarithmic_x':
            # Increase overall speed, weighted toward X axis.
            # Scale both components to preserve trajectory angle.
            self.speed.x *= multiplier
            self.speed.y *= multiplier
        elif speed_up_type == 'logarithmic_y':
            # Increase overall speed, weighted toward Y axis.
            # Scale both components to preserve trajectory angle.
            self.speed.x *= multiplier
            self.speed.y *= multiplier
        elif speed_up_type == 'exponential_x':
            # Exponential speed-up based on X magnitude, applied uniformly.
            # Cap the exponent to prevent runaway growth (max 2.0)
            exponent = min(abs(self.speed.x) / 100.0, 2.0)
            effective_multiplier = multiplier**exponent
            self.speed.x *= effective_multiplier
            self.speed.y *= effective_multiplier
        elif speed_up_type == 'exponential_y':
            # Exponential speed-up based on Y magnitude, applied uniformly.
            exponent = min(abs(self.speed.y) / 100.0, 2.0)
            effective_multiplier = multiplier**exponent
            self.speed.x *= effective_multiplier
            self.speed.y *= effective_multiplier
        elif speed_up_type == 'exponential_both':
            # Exponential speed-up using average of both axes
            x_exponent = min(abs(self.speed.x) / 100.0, 2.0)
            y_exponent = min(abs(self.speed.y) / 100.0, 2.0)
            average_exponent = (x_exponent + y_exponent) / 2.0
            effective_multiplier = multiplier**average_exponent
            self.speed.x *= effective_multiplier
            self.speed.y *= effective_multiplier

    def _check_continuous_speed_up(self: Self, current_time: float) -> None:
        """Check if continuous speed-up should be applied.

        Args:
            current_time (float): Current time in seconds.

        """
        if current_time - self._last_speed_up_time >= self.speed_up_interval:
            # Check for both X and Y exponential speed-up first (highest priority)
            if (
                self.speed_up_mode & SpeedUpMode.CONTINUOUS_EXPONENTIAL_X
                and self.speed_up_mode & SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y
            ):
                self.speed_up(speed_up_type='exponential_both')
                self._last_speed_up_time = current_time
            # Check for both X and Y logarithmic speed-up
            elif (
                self.speed_up_mode & SpeedUpMode.CONTINUOUS_LOGARITHMIC_X
                and self.speed_up_mode & SpeedUpMode.CONTINUOUS_LOGARITHMIC_Y
            ):
                self.speed_up(speed_up_type='logarithmic_both')
                self._last_speed_up_time = current_time
            # Check for exponential X speed-up
            elif self.speed_up_mode & SpeedUpMode.CONTINUOUS_EXPONENTIAL_X:
                self.speed_up(speed_up_type='exponential_x')
                self._last_speed_up_time = current_time
            # Check for exponential Y speed-up
            elif self.speed_up_mode & SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y:
                self.speed_up(speed_up_type='exponential_y')
                self._last_speed_up_time = current_time
            # Check for logarithmic X speed-up
            elif self.speed_up_mode & SpeedUpMode.CONTINUOUS_LOGARITHMIC_X:
                self.speed_up(speed_up_type='logarithmic_x')
                self._last_speed_up_time = current_time
            # Check for logarithmic Y speed-up
            elif self.speed_up_mode & SpeedUpMode.CONTINUOUS_LOGARITHMIC_Y:
                self.speed_up(speed_up_type='logarithmic_y')
                self._last_speed_up_time = current_time
            # Check for linear speed-up
            elif self.speed_up_mode & SpeedUpMode.CONTINUOUS_LINEAR:
                self.speed_up(speed_up_type='linear')
                self._last_speed_up_time = current_time

    def _resolve_speed_up_type(
        self: Self,
        exponential_x_flag: int,
        exponential_y_flag: int,
        logarithmic_x_flag: int,
        logarithmic_y_flag: int,
        linear_flag: int,
    ) -> str | None:
        """Resolve which speed-up type to apply given a set of mode flags.

        Checks from highest priority (exponential both) to lowest (linear).

        Args:
            exponential_x_flag: SpeedUpMode flag for exponential X.
            exponential_y_flag: SpeedUpMode flag for exponential Y.
            logarithmic_x_flag: SpeedUpMode flag for logarithmic X.
            logarithmic_y_flag: SpeedUpMode flag for logarithmic Y.
            linear_flag: SpeedUpMode flag for linear.

        Returns:
            The speed-up type string, or None if no flag matched.

        """
        # Priority-ordered checks: combined flags first, then individual, then linear
        # Each entry is (required_flags_tuple, speed_up_type_name)
        priority_checks: list[tuple[tuple[int, ...], str]] = [
            ((exponential_x_flag, exponential_y_flag), 'exponential_both'),
            ((logarithmic_x_flag, logarithmic_y_flag), 'logarithmic_both'),
            ((exponential_x_flag,), 'exponential_x'),
            ((exponential_y_flag,), 'exponential_y'),
            ((logarithmic_x_flag,), 'logarithmic_x'),
            ((logarithmic_y_flag,), 'logarithmic_y'),
            ((linear_flag,), 'linear'),
        ]

        for required_flags, speed_up_type in priority_checks:
            if all(self.speed_up_mode & flag for flag in required_flags):
                return speed_up_type

        return None

    def _check_bounce_speed_up(self: Self, bounce_type: str) -> None:
        """Check if speed-up should be applied based on bounce type.

        Args:
            bounce_type (str): Type of bounce ('paddle' or 'wall').

        """
        if bounce_type == 'paddle':
            speed_up_type = self._resolve_speed_up_type(
                SpeedUpMode.ON_BOUNCE_EXPONENTIAL_X,
                SpeedUpMode.ON_BOUNCE_EXPONENTIAL_Y,
                SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X,
                SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y,
                SpeedUpMode.ON_BOUNCE_LINEAR,
            )
        elif bounce_type == 'wall':
            speed_up_type = self._resolve_speed_up_type(
                SpeedUpMode.ON_WALL_BOUNCE_EXPONENTIAL_X,
                SpeedUpMode.ON_WALL_BOUNCE_EXPONENTIAL_Y,
                SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X,
                SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y,
                SpeedUpMode.ON_WALL_BOUNCE_LINEAR,
            )
        else:
            speed_up_type = None

        if speed_up_type is not None:
            self.speed_up(speed_up_type=speed_up_type)

    def on_paddle_bounce(self: Self) -> None:
        """Trigger paddle bounce logarithmic speed-up if enabled.

        Args:
            None

        """
        self._check_bounce_speed_up('paddle')

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Update the ball with delta time.

        Args:
            dt (float): The delta time.

        """
        # Check for continuous speed-up
        current_time = time.time()
        self._check_continuous_speed_up(current_time)

        # Apply velocity to sub-pixel position, then sync to rect for rendering
        self.world_x += self.speed.x * dt
        self.world_y += self.speed.y * dt
        self.rect.x = round(self.world_x)
        self.rect.y = round(self.world_y)

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

        # Vertical boundaries are handled by bounce(), not reset.

    @override
    def update(self: Self) -> None:
        """Update the ball.

        Args:
            None

        """
        # Movement is now handled in dt_tick() for frame-rate independence
        # This method is kept for compatibility but no longer moves the ball

    def _do_bounce(self: Self) -> None:
        """Enhanced ball boundary physics with improved collision response.

        Args:
            None

        """
        log.debug(
            f'BALL BOUNCE CHECK: pos=({self.rect.x},{self.rect.y}) '
            f'speed=({self.speed.x:.3f},{self.speed.y:.3f}) '
            f'screen=({self.screen_width},{self.screen_height}) '
            f'bounce_top_bottom={self.bounce_top_bottom} '
            f'bounce_left_right={self.bounce_left_right}',
        )

        # Enhanced boundary checking with proper physics
        self._handle_boundary_collisions(log)

    def _handle_boundary_collisions(self: Self, log: logging.Logger) -> None:
        """Handle boundary collisions with enhanced physics.

        Args:
            log (logging.Logger): Logger instance for debug output

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

    def _handle_top_collision(self: Self, log: logging.Logger) -> None:
        """Handle collision with top boundary with realistic physics.

        Args:
            log (logging.Logger): Logger instance for debug output

        """
        if hasattr(self, 'snd') and self.snd is not None:  # type: ignore[reportUnnecessaryComparison]
            self.snd.play()

        # Reflect off top boundary, preserving remaining distance
        overshoot = -self.world_y  # how far past y=0
        self.world_y = overshoot  # bounce back by overshoot amount
        self.speed.y = abs(self.speed.y)  # ensure downward
        self.rect.y = round(self.world_y)

        self._add_collision_visual_feedback('top', log)
        self._check_bounce_speed_up('wall')

    def _handle_bottom_collision(self: Self, log: logging.Logger) -> None:
        """Handle collision with bottom boundary.

        Args:
            log (logging.Logger): Logger instance for debug output

        """
        if hasattr(self, 'snd') and self.snd is not None:  # type: ignore[reportUnnecessaryComparison]
            self.snd.play()

        # Reflect off bottom boundary, preserving remaining distance
        boundary = float(self.screen_height - self.height)
        overshoot = self.world_y - boundary
        self.world_y = boundary - overshoot
        self.speed.y = -abs(self.speed.y)  # ensure upward
        self.rect.y = round(self.world_y)

        self._add_collision_visual_feedback('bottom', log)
        self._check_bounce_speed_up('wall')

    def _handle_left_collision(self: Self, log: logging.Logger) -> None:
        """Handle collision with left boundary.

        Args:
            log (logging.Logger): Logger instance for debug output

        """
        if hasattr(self, 'snd') and self.snd is not None:  # type: ignore[reportUnnecessaryComparison]
            self.snd.play()

        # Reflect off left boundary, preserving remaining distance
        overshoot = -self.world_x  # how far past x=0
        self.world_x = overshoot
        self.speed.x = abs(self.speed.x)  # ensure rightward
        self.rect.x = round(self.world_x)

        self._add_collision_visual_feedback('left', log)
        self._check_bounce_speed_up('wall')

    def _handle_right_collision(self: Self, log: logging.Logger) -> None:
        """Handle collision with right boundary.

        Args:
            log (logging.Logger): Logger instance for debug output

        """
        if hasattr(self, 'snd') and self.snd is not None:  # type: ignore[reportUnnecessaryComparison]
            self.snd.play()

        # Reflect off right boundary, preserving remaining distance
        boundary = float(self.screen_width - self.width)
        overshoot = self.world_x - boundary
        self.world_x = boundary - overshoot
        self.speed.x = -abs(self.speed.x)  # ensure leftward
        self.rect.x = round(self.world_x)

        self._add_collision_visual_feedback('right', log)
        self._check_bounce_speed_up('wall')

    def _handle_corner_collision(self: Self, log: logging.Logger) -> None:
        """Handle corner collisions with enhanced physics and visual feedback.

        Args:
            log (logging.Logger): Logger instance for debug output

        """
        # Check if ball is in a corner position - include boundary contact
        in_top_left = self.rect.y <= 0 and self.rect.x <= 0
        in_top_right = self.rect.y <= 0 and self.rect.x + self.width >= self.screen_width
        in_bottom_left = self.rect.y + self.height >= self.screen_height and self.rect.x <= 0
        in_bottom_right = (
            self.rect.y + self.height >= self.screen_height
            and self.rect.x + self.width >= self.screen_width
        )

        if in_top_left or in_top_right or in_bottom_left or in_bottom_right:
            log.debug(
                'BALL CORNER COLLISION: %s %s %s %s',
                in_top_left,
                in_top_right,
                in_bottom_left,
                in_bottom_right,
            )

            # Enhanced corner physics - both X and Y components are reflected
            speed_magnitude = math.sqrt(self.speed.x**2 + self.speed.y**2)
            if speed_magnitude > 0:
                # Corner collision: reflect both velocity components
                self.speed.x = -self.speed.x
                self.speed.y = -self.speed.y

                # Add special visual feedback for corner collisions
                self._add_collision_visual_feedback('corner', log)

            # For corner collisions, place ball just inside the corner
            if in_top_left:
                self.world_x = 1.0
                self.world_y = 1.0
            elif in_top_right:
                self.world_x = float(self.screen_width - self.width - 1)
                self.world_y = 1.0
            elif in_bottom_left:
                self.world_x = 1.0
                self.world_y = float(self.screen_height - self.height - 1)
            elif in_bottom_right:
                self.world_x = float(self.screen_width - self.width - 1)
                self.world_y = float(self.screen_height - self.height - 1)
            self.rect.x = round(self.world_x)
            self.rect.y = round(self.world_y)

    def _add_collision_visual_feedback(
        self: Self,
        collision_type: str,
        log: logging.Logger,
    ) -> None:
        """Add visual feedback for collision points and bounce directions.

        Args:
            collision_type (str): Type of collision ("top", "bottom", "left", "right", "corner")
            log (logging.Logger): Logger instance for debug output

        """
        # Visual feedback implementation
        # This could include:
        # - Particle effects at collision point
        # - Screen shake
        # - Color changes
        # - Trail effects showing bounce direction

        # For now, we'll add debug logging and prepare for future visual effects
        log.debug(
            f'BALL COLLISION VISUAL FEEDBACK: {collision_type} at ({self.rect.x}, {self.rect.y})',
        )

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

        """
        # Get all paddle sprites from the same groups as this ball
        paddle_sprites = [
            sprite
            for group in self.groups()
            for sprite in group
            if (hasattr(sprite, 'snd') or sprite.__class__.__name__.lower().find('paddle') != -1)
            and sprite != self
        ]

        # Check collision with each paddle
        for paddle in paddle_sprites:
            assert paddle.rect is not None
            if self.rect.colliderect(paddle.rect):
                # Ball is overlapping with paddle - adjust position to prevent clipping
                self._adjust_position_for_paddle_collision(paddle)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]

    def _adjust_position_for_paddle_collision(self: Self, paddle: Sprite) -> None:
        """Adjust ball position to prevent clipping through paddle and make it bounce.

        Args:
            paddle (Sprite): The paddle sprite that the ball is colliding with

        """
        assert paddle.rect is not None
        # Determine which side of the paddle the ball is on
        ball_center_x = self.rect.centerx
        paddle_center_x = paddle.rect.centerx

        if ball_center_x < paddle_center_x:
            # Ball is on the left side of paddle - position ball to the left
            self.world_x = float(paddle.rect.left - self.rect.width)
            self.speed.x = -abs(self.speed.x)
        else:
            # Ball is on the right side of paddle - position ball to the right
            self.world_x = float(paddle.rect.right)
            self.speed.x = abs(self.speed.x)
        self.rect.x = round(self.world_x)

        # Play collision sound if paddle has one
        paddle_sound = getattr(paddle, 'snd', None)
        if paddle_sound is not None:
            paddle_sound.play()

        # Speed-up on paddle collision, with cap to prevent runaway physics.
        # Only apply speed-up if below the cap to avoid oscillation where
        # speed-up pushes past the cap, gets clamped, then repeats.
        max_speed = 500.0
        speed_magnitude = math.sqrt(self.speed.x**2 + self.speed.y**2)
        if speed_magnitude < max_speed:
            self._check_bounce_speed_up('paddle')

        # Always clamp to max speed (handles both speed-up overshoot
        # and balls that entered the collision already above cap)
        capped_magnitude = math.sqrt(self.speed.x**2 + self.speed.y**2)
        if capped_magnitude > max_speed:
            scale_factor = max_speed / capped_magnitude
            self.speed.x *= scale_factor
            self.speed.y *= scale_factor

        # Notify the game that a paddle collision occurred (for ball spawn)
        collision_callback = getattr(self, 'on_paddle_collision', None)
        if callable(collision_callback):
            collision_callback(self)

        # Mark ball as dirty for redraw
        self.dirty = 2
