"""Papyrus Edition player sprite using TOML animation system."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.examples.brave_adventurer_papyrus.constants import (
    FALLING_VELOCITY_THRESHOLD,
    GRAVITY,
    JUMP_VELOCITY,
    JUMPING_VELOCITY_THRESHOLD,
    LAYER_PLAYER,
    MAX_FALL_SPEED,
    MOVING_VELOCITY_THRESHOLD,
    PLAYER_ACCELERATION,
    PLAYER_DECELERATION,
    PLAYER_RUN_SPEED,
    SPRITES_DIR,
    STARTING_LIVES,
)
from glitchygames.examples.brave_adventurer_papyrus.sprite_utils import (
    apply_transparency_and_scale,
    prepare_papyrus_sprite,
)
from glitchygames.sprites import AnimatedSprite

if TYPE_CHECKING:
    from glitchygames.camera import Camera2D


def _ramp_velocity(
    current: float,
    target: float,
    acceleration: float,
    deceleration: float,
    dt: float,
) -> float:
    """Smoothly ramp a velocity toward a target value.

    Uses acceleration when moving toward a nonzero target, and
    deceleration when slowing to zero.

    Args:
        current: Current velocity.
        target: Target velocity.
        acceleration: Rate of change when accelerating (pixels/sec^2).
        deceleration: Rate of change when decelerating (pixels/sec^2).
        dt: Delta time in seconds.

    Returns:
        The new velocity value.

    """
    if target != 0.0:  # noqa: RUF069 - exact float comparison is intentional
        difference = target - current
        max_change = acceleration * dt
        if abs(difference) <= max_change:
            return target
        return current + max_change if difference > 0 else current - max_change

    if current == 0.0:  # noqa: RUF069 - exact float comparison is intentional
        return 0.0

    max_change = deceleration * dt
    if abs(current) <= max_change:
        return 0.0
    return current - max_change if current > 0 else current + max_change


class PapyrusPlayer(AnimatedSprite):
    """Adventurer character using TOML sprite animations with platformer physics.

    Extends AnimatedSprite for TOML rendering. Physics logic (gravity, jumping,
    velocity) is self-contained to avoid diamond inheritance with the engine's
    Sprite class.
    """

    IDLE = 'idle'
    RUNNING = 'running'
    JUMPING = 'jumping'
    FALLING = 'falling'

    def __init__(
        self,
        world_x: float,
        world_y: float,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Initialize the papyrus player.

        Args:
            world_x: Starting X position in world coordinates.
            world_y: Starting Y position in world coordinates.
            groups: The sprite group to add this sprite to.

        """
        self._layer = LAYER_PLAYER

        super().__init__(
            filename=str(SPRITES_DIR / 'player.toml'),
            groups=groups,
        )

        # Scale up TOML pixel art and set magenta transparency
        prepare_papyrus_sprite(self)

        # World-space position (floats for sub-pixel accuracy)
        self.world_x: float = world_x
        self.world_y: float = world_y
        self.rect.x = round(world_x)
        self.rect.y = round(world_y)

        # Velocity in pixels per second
        self.velocity_x: float = 0.0
        self.velocity_y: float = 0.0
        self._target_velocity_x: float = 0.0

        # State
        self.on_ground: bool = False
        self.state: str = self.IDLE
        self.facing_right: bool = True

        # Delta time tracking (AnimatedSprite doesn't have this)
        self.dt: float = 0.0
        self.dt_timer: float = 0.0

        # Game state
        self.lives: int = STARTING_LIVES
        self.score: int = 0
        self.max_distance: float = 0.0

        # Visual effects
        self.alpha: float = 255.0
        self.is_respawning: bool = False

        # Start idle animation
        self.play(self.IDLE)
        self.is_looping = True
        self.dirty = 2

    def dt_tick(self: Self, dt: float) -> None:
        """Apply gravity and velocity, advance animation, detect state changes.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        self.dt = dt
        self.dt_timer += dt

        # Ramp horizontal velocity toward target (acceleration/deceleration)
        self.velocity_x = _ramp_velocity(
            current=self.velocity_x,
            target=self._target_velocity_x,
            acceleration=PLAYER_ACCELERATION,
            deceleration=PLAYER_DECELERATION,
            dt=dt,
        )

        # Apply gravity (capped at terminal velocity)
        self.velocity_y = min(self.velocity_y + GRAVITY * dt, MAX_FALL_SPEED)

        # Apply velocity to world position
        self.world_x += self.velocity_x * dt
        self.world_y += self.velocity_y * dt

        # Prevent going left of world origin
        if self.world_x < 0:
            self.world_x = 0.0
            self.velocity_x = 0.0

        # Detect state change and switch animation
        new_state = self._detect_state()
        if new_state != self.state:
            self.state = new_state
            self.play(self.state)
            self.is_looping = self.state in {self.IDLE, self.RUNNING}

        # Advance TOML animation frames and fix transparency
        AnimatedSprite.update(self, dt)
        apply_transparency_and_scale(self)

        # Flip image when facing left
        if not self.facing_right:
            self.image = pygame.transform.flip(self.image, flip_x=True, flip_y=False)

        # Apply alpha for respawn fade effect
        self.image.set_alpha(round(self.alpha))

    def _detect_state(self) -> str:
        """Determine the current animation state from physics.

        Returns:
            The state string matching a TOML animation namespace.

        """
        if self.velocity_y < JUMPING_VELOCITY_THRESHOLD:
            return self.JUMPING
        if self.velocity_y > FALLING_VELOCITY_THRESHOLD and not self.on_ground:
            return self.FALLING
        if abs(self.velocity_x) > MOVING_VELOCITY_THRESHOLD:
            return self.RUNNING
        return self.IDLE

    def jump(self) -> None:
        """Initiate a jump if the player is on the ground."""
        if self.on_ground:
            self.velocity_y = JUMP_VELOCITY
            self.on_ground = False

    def move_right(self) -> None:
        """Start moving right with smooth acceleration."""
        self._target_velocity_x = PLAYER_RUN_SPEED
        self.facing_right = True

    def move_left(self) -> None:
        """Start moving left with smooth acceleration."""
        self._target_velocity_x = -PLAYER_RUN_SPEED
        self.facing_right = False

    def stop_horizontal(self) -> None:
        """Smoothly decelerate to a stop."""
        self._target_velocity_x = 0.0

    def apply_camera(self, camera: Camera2D) -> None:
        """Update the screen-space rect from world coordinates using the camera.

        Args:
            camera: The camera providing the world-to-screen transform.

        """
        screen_x, screen_y = camera.apply(self.world_x, self.world_y)
        self.rect.x = screen_x
        self.rect.y = screen_y

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """No-op. Animation is advanced in dt_tick() instead."""
