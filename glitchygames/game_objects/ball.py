#!/usr/bin/env python3
"""Ball."""

from __future__ import annotations

import logging
import math
import secrets
from dataclasses import dataclass
from enum import Enum, Flag, auto
from typing import TYPE_CHECKING, NamedTuple, Self, override

if TYPE_CHECKING:
    from collections.abc import Callable

import pygame

from glitchygames import game_objects
from glitchygames.collision.detection import get_collision_rect, snapped_world_position
from glitchygames.collision.layers import get_sprite_collision_rect
from glitchygames.color import WHITE
from glitchygames.movement import Speed

# PixelSnapMode and snap_to_pixel moved to glitchygames.pixel_snap (with HALF_PIXEL, which
# only snap_to_pixel uses) so collision code can share them; importing them here keeps
# `from glitchygames.game_objects.ball import PixelSnapMode, snap_to_pixel` working.
from glitchygames.pixel_snap import PixelSnapMode, snap_to_pixel
from glitchygames.sprites import Sprite

log: logging.Logger = logging.getLogger('game.objects.ball')

# Threshold below which speed changes are considered noise
SPEED_CHANGE_NOISE_FLOOR = 0.001

# Minimum Y movement to be considered significant for logging
SIGNIFICANT_MOVEMENT_THRESHOLD = 0.1

# Seconds of slack when deciding a CONTINUOUS speed-up is due, so float accumulation
# (ten 0.1 s frames sum to 0.9999999999999999) cannot delay it by a frame
CONTINUOUS_SPEED_UP_TIME_TOLERANCE = 1e-9

# Steepest allowed serve angle from horizontal (straight up or down)
MAXIMUM_SERVE_ANGLE_DEGREES = 90.0


class VisibleRect(NamedTuple):
    """A ball's visible collision rect and its offset from the drawn (snapped) position."""

    left: int
    top: int
    width: int
    height: int
    offset_x: int  # visible left minus the snapped world x
    offset_y: int  # visible top minus the snapped world y

    @property
    def right(self) -> int:
        """The visible right edge (exclusive, like pygame.Rect.right)."""
        return self.left + self.width

    @property
    def bottom(self) -> int:
        """The visible bottom edge (exclusive, like pygame.Rect.bottom)."""
        return self.top + self.height


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


class SpeedUpCurve(Enum):
    """How speed grows over successive speed-ups.

    With base speed s0, n speed-ups so far, and growth k = multiplier - 1:
    - LINEAR: s0 * (1 + n*k), the same absolute increase every time.
    - EXPONENTIAL: s0 * multiplier**n, the same percentage increase every time.
    - LOGARITHMIC: s0 * (1 + k*ln(1 + n)), big early boosts that taper off.
    """

    LINEAR = 'linear'
    EXPONENTIAL = 'exponential'
    LOGARITHMIC = 'logarithmic'


class SpeedUpAxes(Enum):
    """Which velocity components a speed-up scales."""

    BOTH = 'both'  # Scale the whole velocity, preserving the trajectory angle
    X_ONLY = 'x_only'  # Scale horizontal speed only; the ball gets flatter over time
    Y_ONLY = 'y_only'  # Scale vertical speed only; the ball gets steeper over time


class SpeedUpTrigger(Flag):
    """Events that cause a speed-up. Combine with |; all triggers share one curve."""

    NONE = 0
    CONTINUOUS = auto()  # Every SpeedUpSettings.interval seconds
    PADDLE_BOUNCE = auto()  # Each paddle hit
    WALL_BOUNCE = auto()  # Each wall bounce


class SpeedUpSchedule(Enum):
    """How CONTINUOUS speed-ups are scheduled against elapsed game time.

    All schedules count game time (the dt passed to dt_tick), so pausing pauses them.
    """

    # Every interval of game time; leftover time carries over so the rate does not
    # depend on frame rate. After a long frame, one speed-up is applied and the extra
    # whole intervals are skipped (no burst). The sane default for most games.
    FIXED_RATE = 'fixed_rate'
    # Every elapsed interval, applying several speed-ups in one frame after a long
    # frame. For deterministic simulations or replays that must match elapsed time.
    CATCH_UP = 'catch_up'
    # The next interval starts when a speed-up fires; leftover time is discarded, so
    # speed-ups are never closer than interval but arrive later at lower frame rates.
    MINIMUM_GAP = 'minimum_gap'


@dataclass(frozen=True)
class SpeedUpSettings:
    """How and when a ball speeds up.

    Attributes:
        triggers: Events that cause a speed-up (NONE disables automatic speed-ups).
        curve: How speed grows over successive speed-ups.
        axes: Which velocity components are scaled.
        multiplier: Growth per speed-up (>= 1.0); its meaning depends on curve.
        interval: Seconds of game time between CONTINUOUS speed-ups.
        schedule: How CONTINUOUS speed-ups are scheduled (see SpeedUpSchedule).
        max_speed: Cap in px/s on the scaled speed (magnitude for BOTH, the single
            component otherwise), or None for no cap.

    """

    triggers: SpeedUpTrigger = SpeedUpTrigger.NONE
    curve: SpeedUpCurve = SpeedUpCurve.EXPONENTIAL
    axes: SpeedUpAxes = SpeedUpAxes.BOTH
    multiplier: float = 1.1
    interval: float = 1.0
    schedule: SpeedUpSchedule = SpeedUpSchedule.FIXED_RATE
    max_speed: float | None = None

    def __post_init__(self) -> None:
        """Reject settings that would stop, reverse, or break the ball.

        Raises:
            ValueError: If a field is outside its valid range.

        """
        if not (math.isfinite(self.multiplier) and self.multiplier >= 1.0):
            msg = f'speed-up multiplier must be a finite number >= 1.0, got {self.multiplier}'
            raise ValueError(msg)
        if not (math.isfinite(self.interval) and self.interval > 0.0):
            msg = f'speed-up interval must be a positive number of seconds, got {self.interval}'
            raise ValueError(msg)
        if self.max_speed is not None and not (
            math.isfinite(self.max_speed) and self.max_speed > 0.0
        ):
            msg = f'max_speed must be None or a positive number, got {self.max_speed}'
            raise ValueError(msg)


def speed_up_step_ratio(curve: SpeedUpCurve, multiplier: float, completed_steps: int) -> float:
    """Return the factor that advances speed from step n to step n + 1 of a curve.

    Applying ratios to the current speed (rather than setting speed from the curve
    directly) keeps changes from collisions between speed-ups, while following the
    curve exactly when nothing else changes the speed.

    Args:
        curve: The growth curve.
        multiplier: Growth per speed-up (>= 1.0).
        completed_steps: Speed-ups already applied (n).

    Returns:
        float: f(n + 1) / f(n) for the curve.

    """
    growth = multiplier - 1.0
    match curve:
        case SpeedUpCurve.LINEAR:
            return (1.0 + (completed_steps + 1) * growth) / (1.0 + completed_steps * growth)
        case SpeedUpCurve.EXPONENTIAL:
            return multiplier
        case SpeedUpCurve.LOGARITHMIC:
            return (1.0 + growth * math.log1p(completed_steps + 1)) / (
                1.0 + growth * math.log1p(completed_steps)
            )


# Single random source for serves (position, side, angle), so tests can pin them all.
# SystemRandom draws from the OS entropy pool, like the secrets module.
_SERVE_RANDOM = secrets.SystemRandom()


class ServeHorizontalDirection(Enum):
    """Which way a serve travels horizontally."""

    LEFT = 'left'
    RIGHT = 'right'
    EITHER = 'either'  # Chosen at random for each serve


class ServeVerticalDirection(Enum):
    """Which way a serve travels vertically (screen y grows downward)."""

    UP = 'up'
    DOWN = 'down'
    EITHER = 'either'  # Chosen at random for each serve


@dataclass(frozen=True)
class ServeSettings:
    """Where and how a ball is served by reset() and serve().

    The defaults suit Pong-style games: a diagonal serve 15-60 degrees above or below
    horizontal, toward either side. For Breakout-style serves use vertical=UP and a
    steeper band; for a fixed serve set both angles equal and pick single directions.

    Attributes:
        minimum_angle_degrees: Smallest serve angle from horizontal (0-90).
        maximum_angle_degrees: Largest serve angle from horizontal (0-90).
        horizontal: Horizontal direction of the serve.
        vertical: Vertical direction of the serve.
        speed: Serve speed in px/s.
        spawn_margin: Minimum distance in px between a served ball's visible circle
            (its collision rect) and each screen edge; on screens too small for it the
            ball is centered.

    """

    minimum_angle_degrees: float = 15.0
    maximum_angle_degrees: float = 60.0
    horizontal: ServeHorizontalDirection = ServeHorizontalDirection.EITHER
    vertical: ServeVerticalDirection = ServeVerticalDirection.EITHER
    speed: float = 250.0
    spawn_margin: int = 50

    def __post_init__(self) -> None:
        """Reject serve settings outside their valid ranges.

        Raises:
            ValueError: If a field is outside its valid range.

        """
        for field_name in ('minimum_angle_degrees', 'maximum_angle_degrees'):
            angle = getattr(self, field_name)
            if not (math.isfinite(angle) and 0.0 <= angle <= MAXIMUM_SERVE_ANGLE_DEGREES):
                msg = f'{field_name} must be between 0 and 90 degrees, got {angle}'
                raise ValueError(msg)
        if self.minimum_angle_degrees > self.maximum_angle_degrees:
            msg = (
                f'serve angle band is inverted: minimum {self.minimum_angle_degrees} > '
                f'maximum {self.maximum_angle_degrees}'
            )
            raise ValueError(msg)
        if not (math.isfinite(self.speed) and self.speed > 0.0):
            msg = f'speed must be a positive number of px/s, got {self.speed}'
            raise ValueError(msg)
        if self.spawn_margin < 0:
            msg = f'spawn_margin must be >= 0, got {self.spawn_margin}'
            raise ValueError(msg)


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
        speed_up_settings: SpeedUpSettings | None = None,
        serve_settings: ServeSettings | None = None,
        pixel_snap_mode: PixelSnapMode = PixelSnapMode.NEAREST_HALF_UP,
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
            speed_up_settings (SpeedUpSettings | None): How and when the ball speeds up;
                None means SpeedUpSettings() (no automatic speed-ups).
            serve_settings (ServeSettings | None): How reset() and serve() serve the
                ball; None means ServeSettings() (Pong-style diagonal serves).
            pixel_snap_mode (PixelSnapMode): How the sub-pixel world position is rounded
                to the rect position the ball is drawn at.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()  # type: ignore[type-arg]

        super().__init__(x=x, y=y, width=width, height=height, groups=groups)  # type: ignore[arg-type]
        self.use_gfxdraw = True
        self.image.convert()
        self.image.set_colorkey(0)
        self.direction = 0
        self.speed = Speed(250.0, 125.0)  # 250 pixels/second horizontal, 125 pixels/second vertical

        # Sub-pixel position tracking (floats for accurate physics). rect holds the
        # snapped whole-pixel position for rendering and is kept in sync by the
        # world_x/world_y setters, so code should move the ball via world_x/world_y.
        self._pixel_snap_mode = pixel_snap_mode
        self.world_x = float(x)
        self.world_y = float(y)
        if collision_sound:
            self.snd = game_objects.load_sound(collision_sound)
        self.color = WHITE

        # Configure boundary bouncing behavior
        self.bounce_top_bottom = bounce_top_bottom
        self.bounce_left_right = bounce_left_right

        # Configure serve and speed-up behavior
        self.serve_settings = serve_settings or ServeSettings()
        self.speed_up_settings = speed_up_settings or SpeedUpSettings()
        self.speed_up_count = 0  # Speed-ups applied since the last reset (curve step n)
        self._continuous_elapsed_time = 0.0  # Game seconds toward the next CONTINUOUS step

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
    def world_x(self: Self) -> float:
        """The ball's sub-pixel x position."""
        return self._world_x

    @world_x.setter
    def world_x(self: Self, value: float) -> None:
        """Set the sub-pixel x position and snap rect.x to match."""
        self._world_x = value
        self.rect.x = snap_to_pixel(value, self._pixel_snap_mode)

    @property
    def world_y(self: Self) -> float:
        """The ball's sub-pixel y position."""
        return self._world_y

    @world_y.setter
    def world_y(self: Self, value: float) -> None:
        """Set the sub-pixel y position and snap rect.y to match."""
        self._world_y = value
        self.rect.y = snap_to_pixel(value, self._pixel_snap_mode)

    @property
    def pixel_snap_mode(self: Self) -> PixelSnapMode:
        """How the sub-pixel world position is rounded to the drawn rect position."""
        return self._pixel_snap_mode

    @pixel_snap_mode.setter
    def pixel_snap_mode(self: Self, mode: PixelSnapMode) -> None:
        """Change the snap mode and immediately re-snap rect to the world position."""
        self._pixel_snap_mode = mode
        self.world_x = self._world_x
        self.world_y = self._world_y

    @property
    def color(self: Self) -> tuple[int, int, int]:
        """The color of the ball.

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

    def reset(self: Self, serve_toward: ServeHorizontalDirection | None = None) -> None:
        """Start a new serve: random position within the spawn margin, then serve().

        Also restarts the speed-up curve and the continuous speed-up timer.

        Args:
            serve_toward (ServeHorizontalDirection | None): Override the horizontal
                direction for this serve (e.g. toward the player who lost the point).

        """
        self.speed_up_count = 0
        self._continuous_elapsed_time = 0.0

        # The margin is measured from the visible circle (the collision rect) to each edge
        margin = self.serve_settings.spawn_margin
        visible_rect = self._visible_rect()
        self.world_x = float(
            self._random_spawn_coordinate(int(self.screen_width - visible_rect.width), margin)
            - visible_rect.offset_x
        )
        self.world_y = float(
            self._random_spawn_coordinate(int(self.screen_height - visible_rect.height), margin)
            - visible_rect.offset_y
        )
        self.serve(serve_toward=serve_toward)

    @staticmethod
    def _random_spawn_coordinate(maximum_position: int, margin: int) -> int:
        """Pick a visible-edge coordinate in [margin, maximum_position - margin], or center.

        Returns:
            int: The coordinate (never negative).

        """
        lowest = margin
        highest = maximum_position - margin
        if lowest > highest:
            return max(maximum_position // 2, 0)
        return _SERVE_RANDOM.randint(lowest, highest)

    def serve(self: Self, serve_toward: ServeHorizontalDirection | None = None) -> None:
        """Set a serve velocity from serve_settings without moving the ball.

        Args:
            serve_toward (ServeHorizontalDirection | None): Override the horizontal
                direction for this serve.

        """
        settings = self.serve_settings
        horizontal = serve_toward or settings.horizontal
        if horizontal is ServeHorizontalDirection.EITHER:
            horizontal = _SERVE_RANDOM.choice((
                ServeHorizontalDirection.LEFT,
                ServeHorizontalDirection.RIGHT,
            ))
        vertical = settings.vertical
        if vertical is ServeVerticalDirection.EITHER:
            vertical = _SERVE_RANDOM.choice((
                ServeVerticalDirection.UP,
                ServeVerticalDirection.DOWN,
            ))

        angle_radians = math.radians(
            _SERVE_RANDOM.uniform(settings.minimum_angle_degrees, settings.maximum_angle_degrees)
        )
        horizontal_sign = 1.0 if horizontal is ServeHorizontalDirection.RIGHT else -1.0
        vertical_sign = 1.0 if vertical is ServeVerticalDirection.DOWN else -1.0
        self.speed.x = horizontal_sign * settings.speed * math.cos(angle_radians)
        self.speed.y = vertical_sign * settings.speed * math.sin(angle_radians)
        # Heading in degrees, 0 = right, 90 = down (kept for debugging and display)
        self.direction = math.degrees(math.atan2(self.speed.y, self.speed.x)) % 360

    def speed_up(self: Self) -> None:
        """Apply one speed-up step according to speed_up_settings.

        Scales the configured axes by the curve's next step ratio, then applies
        max_speed. Changes made to speed between steps (collisions) are kept.
        """
        settings = self.speed_up_settings
        ratio = speed_up_step_ratio(settings.curve, settings.multiplier, self.speed_up_count)
        self.speed_up_count += 1
        if settings.axes is not SpeedUpAxes.Y_ONLY:
            self.speed.x *= ratio
        if settings.axes is not SpeedUpAxes.X_ONLY:
            self.speed.y *= ratio
        self._clamp_to_max_speed()

    def _clamp_to_max_speed(self: Self) -> None:
        """Limit the configured axes to speed_up_settings.max_speed, if one is set."""
        settings = self.speed_up_settings
        if settings.max_speed is None:
            return
        match settings.axes:
            case SpeedUpAxes.BOTH:
                speed_magnitude = math.hypot(self.speed.x, self.speed.y)
                if speed_magnitude > settings.max_speed:
                    scale_factor = settings.max_speed / speed_magnitude
                    self.speed.x *= scale_factor
                    self.speed.y *= scale_factor
            case SpeedUpAxes.X_ONLY:
                if abs(self.speed.x) > settings.max_speed:
                    self.speed.x = math.copysign(settings.max_speed, self.speed.x)
            case SpeedUpAxes.Y_ONLY:
                if abs(self.speed.y) > settings.max_speed:
                    self.speed.y = math.copysign(settings.max_speed, self.speed.y)

    def _advance_continuous_speed_up(self: Self, dt: float) -> None:
        """Advance the CONTINUOUS speed-up timer by dt seconds of game time.

        Args:
            dt (float): Game time elapsed this frame, in seconds.

        """
        settings = self.speed_up_settings
        if SpeedUpTrigger.CONTINUOUS not in settings.triggers:
            return
        self._continuous_elapsed_time += dt
        intervals_due = math.floor(
            (self._continuous_elapsed_time + CONTINUOUS_SPEED_UP_TIME_TOLERANCE) / settings.interval
        )
        if intervals_due < 1:
            return
        match settings.schedule:
            case SpeedUpSchedule.FIXED_RATE:
                self.speed_up()
                self._continuous_elapsed_time -= intervals_due * settings.interval
            case SpeedUpSchedule.CATCH_UP:
                for _ in range(intervals_due):
                    self.speed_up()
                self._continuous_elapsed_time -= intervals_due * settings.interval
            case SpeedUpSchedule.MINIMUM_GAP:
                self.speed_up()
                self._continuous_elapsed_time = 0.0
        # The tolerance can leave a tiny negative remainder
        self._continuous_elapsed_time = max(self._continuous_elapsed_time, 0.0)

    def _apply_triggered_speed_up(self: Self, trigger: SpeedUpTrigger) -> None:
        """Speed up if the given event is one of the configured triggers.

        Args:
            trigger (SpeedUpTrigger): The event that just happened.

        """
        if trigger in self.speed_up_settings.triggers:
            self.speed_up()

    def on_paddle_bounce(self: Self) -> None:
        """Speed up for a paddle hit if PADDLE_BOUNCE is a configured trigger.

        Args:
            None

        """
        self._apply_triggered_speed_up(SpeedUpTrigger.PADDLE_BOUNCE)

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Update the ball with delta time.

        Args:
            dt (float): The delta time.

        """
        # Check for continuous speed-up
        self._advance_continuous_speed_up(dt)

        # Apply velocity to sub-pixel position (the setters sync rect for rendering)
        self.world_x += self.speed.x * dt
        self.world_y += self.speed.y * dt

        # Ensure the ball is marked as dirty for redrawing
        self.dirty = 1

        # Paddle hits are found by the game's CollisionManager after the balls move and
        # resolved by handle_paddle_collision() (see PaddleSlap's update()).

        self._do_bounce()

        # Only kill ball once its visible circle is fully off screen and left/right
        # bouncing is disabled
        if not self.bounce_left_right:
            visible_rect = self._visible_rect()
            if visible_rect.left > self.screen_width or visible_rect.right < 0:
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
        """Bounce off any wall the ball is touching while moving toward it.

        A frame that hits one wall, or two at a corner, is a single bounce: one sound
        and at most one WALL_BOUNCE speed-up. A ball touching a wall while already
        moving away from it (e.g. the frame after a bounce) does not bounce again.

        Args:
            log (logging.Logger): Logger instance for debug output

        """
        hit_horizontal_wall = False  # top or bottom
        hit_vertical_wall = False  # left or right

        # Contact is on the visible circle's box at the snapped (drawn) position
        visible_rect = self._visible_rect()

        if self.bounce_top_bottom:
            if visible_rect.top <= 0 and self.speed.y < 0:
                self._handle_top_collision(log)
                hit_horizontal_wall = True
            elif visible_rect.bottom >= self.screen_height and self.speed.y > 0:
                self._handle_bottom_collision(log)
                hit_horizontal_wall = True

        if self.bounce_left_right:
            if visible_rect.left <= 0 and self.speed.x < 0:
                self._handle_left_collision(log)
                hit_vertical_wall = True
            elif visible_rect.right >= self.screen_width and self.speed.x > 0:
                self._handle_right_collision(log)
                hit_vertical_wall = True

        if hit_horizontal_wall and hit_vertical_wall:
            self._handle_corner_collision(log)

        if hit_horizontal_wall or hit_vertical_wall:
            if hasattr(self, 'snd') and self.snd is not None:  # type: ignore[reportUnnecessaryComparison]
                self.snd.play()
            self._apply_triggered_speed_up(SpeedUpTrigger.WALL_BOUNCE)

        self._keep_inside_playfield()

    def _keep_inside_playfield(self: Self) -> None:
        """Mirror any overshoot past a bouncing wall back inside the playfield.

        Runs whether or not the ball bounced this frame, so a ball found past a wall
        while moving away from it (or not moving) is still put back inside. The limits
        are where the visible circle's edges meet the walls.
        """
        visible_rect = self._visible_rect()
        if self.bounce_top_bottom:
            self.world_y = self._mirrored_inside(
                self.world_y,
                minimum=float(-visible_rect.offset_y),
                maximum=float(self.screen_height - visible_rect.height - visible_rect.offset_y),
            )
        if self.bounce_left_right:
            self.world_x = self._mirrored_inside(
                self.world_x,
                minimum=float(-visible_rect.offset_x),
                maximum=float(self.screen_width - visible_rect.width - visible_rect.offset_x),
            )

    @staticmethod
    def _mirrored_inside(position: float, *, minimum: float, maximum: float) -> float:
        """Mirror a position that overshot [minimum, maximum] back inside, clamping huge ones.

        Returns:
            float: The position within [minimum, maximum].

        """
        if position < minimum:
            position = 2.0 * minimum - position
        elif position > maximum:
            position = 2.0 * maximum - position
        return min(max(position, minimum), maximum)

    def _visible_rect(self: Self) -> VisibleRect:
        """Return the ball's visible collision rect and its offset from the drawn position.

        The rect is the same one collision checks use (get_collision_rect: the visible
        pixels of the image at the snapped world position), so walls, paddles and other
        balls all meet the circle players see.

        Returns:
            VisibleRect: The rect plus its offset from the snapped world position.

        """
        collision_rect = get_collision_rect(self, self.world_x, self.world_y)
        snapped_world_x, snapped_world_y = snapped_world_position(self, self.world_x, self.world_y)
        return VisibleRect(
            left=collision_rect.left,
            top=collision_rect.top,
            width=collision_rect.width,
            height=collision_rect.height,
            offset_x=collision_rect.x - snapped_world_x,
            offset_y=collision_rect.y - snapped_world_y,
        )

    def _handle_top_collision(self: Self, log: logging.Logger) -> None:
        """Reflect the velocity off the top wall.

        Position is corrected afterwards by _keep_inside_playfield(), which mirrors
        only a real overshoot (contact is detected on the snapped rect, so the world
        position may already be just inside the wall).

        Args:
            log (logging.Logger): Logger instance for debug output

        """
        self.speed.y = abs(self.speed.y)  # ensure downward
        self._add_collision_visual_feedback('top', log)

    def _handle_bottom_collision(self: Self, log: logging.Logger) -> None:
        """Reflect the velocity off the bottom wall (see _handle_top_collision).

        Args:
            log (logging.Logger): Logger instance for debug output

        """
        self.speed.y = -abs(self.speed.y)  # ensure upward
        self._add_collision_visual_feedback('bottom', log)

    def _handle_left_collision(self: Self, log: logging.Logger) -> None:
        """Reflect the velocity off the left wall (see _handle_top_collision).

        Args:
            log (logging.Logger): Logger instance for debug output

        """
        self.speed.x = abs(self.speed.x)  # ensure rightward
        self._add_collision_visual_feedback('left', log)

    def _handle_right_collision(self: Self, log: logging.Logger) -> None:
        """Reflect the velocity off the right wall (see _handle_top_collision).

        Args:
            log (logging.Logger): Logger instance for debug output

        """
        self.speed.x = -abs(self.speed.x)  # ensure leftward
        self._add_collision_visual_feedback('right', log)

    def _handle_corner_collision(self: Self, log: logging.Logger) -> None:
        """Give visual feedback for a bounce that hit two walls in the same frame.

        The edge handlers have already reflected both velocity components, and
        _keep_inside_playfield() corrects position, so this must not change either.

        Args:
            log (logging.Logger): Logger instance for debug output

        """
        log.debug(
            'BALL CORNER COLLISION: pos=(%s, %s) speed=(%.3f, %.3f)',
            self.rect.x,
            self.rect.y,
            self.speed.x,
            self.speed.y,
        )
        self._add_collision_visual_feedback('corner', log)

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

    def handle_paddle_collision(self: Self, paddle: Sprite) -> bool:
        """Bounce off a paddle if the ball's visible circle touches it.

        Meant as the fine check after a CollisionManager broad-phase overlap. The ball is
        the circle inscribed in its collision rect (its visible pixels); the paddle is its
        collision rect. Touching counts. On a hit the ball is placed with its visible edge
        flush against the paddle face on its side (decided by collision-rect centres), its
        horizontal speed points away from the paddle, the paddle's sound plays, a
        PADDLE_BOUNCE speed-up and the max_speed clamp are applied, and on_paddle_collision
        is called.

        Args:
            paddle (Sprite): The paddle the broad phase paired with this ball.

        Returns:
            bool: True if the ball hit the paddle and bounced; False (with no side effects)
            otherwise.

        """
        ball_rect = self._visible_rect()
        paddle_rect = get_sprite_collision_rect(paddle)

        radius = ball_rect.width / 2
        ball_center_x = ball_rect.left + ball_rect.width / 2
        ball_center_y = ball_rect.top + ball_rect.height / 2
        closest_x = min(max(ball_center_x, paddle_rect.left), paddle_rect.right)
        closest_y = min(max(ball_center_y, paddle_rect.top), paddle_rect.bottom)
        distance_squared = (ball_center_x - closest_x) ** 2 + (ball_center_y - closest_y) ** 2
        if distance_squared > radius * radius:
            return False

        visible_offset_x = ball_rect.offset_x
        paddle_center_x = paddle_rect.x + paddle_rect.width / 2

        if ball_center_x < paddle_center_x:
            # Ball is on the left side of paddle - visible right edge on the left face
            self.world_x = float(paddle_rect.left - (visible_offset_x + ball_rect.width))
            self.speed.x = -abs(self.speed.x)
        else:
            # Ball is on the right side of paddle - visible left edge on the right face
            self.world_x = float(paddle_rect.right - visible_offset_x)
            self.speed.x = abs(self.speed.x)

        # Play collision sound if paddle has one
        paddle_sound = getattr(paddle, 'snd', None)
        if paddle_sound is not None:
            paddle_sound.play()

        # Speed-up on paddle collision (speed_up() applies max_speed itself). Clamp
        # again in case the ball arrived above max_speed with no speed-up triggered.
        self._apply_triggered_speed_up(SpeedUpTrigger.PADDLE_BOUNCE)
        self._clamp_to_max_speed()

        # Notify the game that a paddle collision occurred (for ball spawn)
        collision_callback = getattr(self, 'on_paddle_collision', None)
        if callable(collision_callback):
            collision_callback(self)

        # Mark ball as dirty for redraw
        self.dirty = 2
        return True
