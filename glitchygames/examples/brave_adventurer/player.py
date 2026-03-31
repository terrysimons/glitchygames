"""Player sprite with platformer physics for Brave Adventurer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, override

import pygame

from glitchygames.examples.brave_adventurer.constants import (
    FALLING_VELOCITY_THRESHOLD,
    GRAVITY,
    JUMP_VELOCITY,
    JUMPING_VELOCITY_THRESHOLD,
    LAYER_PLAYER,
    MAX_FALL_SPEED,
    MOVING_VELOCITY_THRESHOLD,
    PLAYER_ACCELERATION,
    PLAYER_DECELERATION,
    PLAYER_HEIGHT,
    PLAYER_RUN_SPEED,
    PLAYER_WIDTH,
    STARTING_LIVES,
)
from glitchygames.examples.brave_adventurer.drawing import draw_player
from glitchygames.sprites import Sprite

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


class Player(Sprite):
    """The adventurer character with platformer physics.

    Stores world-space coordinates separately from the screen-space rect.
    Physics (gravity, jumping) are applied in dt_tick(). The screen rect
    is updated via apply_camera() before rendering.
    """

    IDLE = 'idle'
    RUNNING = 'running'
    JUMPING = 'jumping'
    FALLING = 'falling'

    def __init__(
        self,
        world_x: float,
        world_y: float,
        groups: pygame.sprite.LayeredDirty[Sprite],
    ) -> None:
        """Initialize the player.

        Args:
            world_x: Starting X position in world coordinates.
            world_y: Starting Y position in world coordinates.
            groups: The sprite group to add this sprite to.

        """
        # Set layer before super().__init__ so LayeredDirty uses it
        self._layer = LAYER_PLAYER

        super().__init__(
            x=world_x,
            y=world_y,
            width=PLAYER_WIDTH,
            height=PLAYER_HEIGHT,
            name='Player',
            groups=groups,
        )

        # Replace default surface with one that supports transparency
        self.image = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT), pygame.SRCALPHA)

        # World-space position (floats for sub-pixel accuracy)
        self.world_x: float = world_x
        self.world_y: float = world_y

        # Velocity in pixels per second
        self.velocity_x: float = 0.0
        self.velocity_y: float = 0.0
        self._target_velocity_x: float = 0.0

        # State
        self.on_ground: bool = False
        self.state: str = self.IDLE
        self.facing_right: bool = True
        self.animation_timer: float = 0.0

        # Game state
        self.lives: int = STARTING_LIVES
        self.score: int = 0
        self.max_distance: float = 0.0

        # Visual effects
        self.alpha: float = 255.0
        self.is_respawning: bool = False

        # Always redraw (position changes every frame due to camera)
        self.dirty = 2

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Apply gravity and velocity to update world position.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        super().dt_tick(dt)
        self.animation_timer += dt

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

        # Update animation state
        if self.velocity_y < JUMPING_VELOCITY_THRESHOLD:
            self.state = self.JUMPING
        elif self.velocity_y > FALLING_VELOCITY_THRESHOLD and not self.on_ground:
            self.state = self.FALLING
        elif abs(self.velocity_x) > MOVING_VELOCITY_THRESHOLD:
            self.state = self.RUNNING
        else:
            self.state = self.IDLE

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
    def update(self: Self) -> None:
        """Redraw the player image based on the current state."""
        self.image.fill((0, 0, 0, 0))
        draw_player(
            self.image,
            self.state,
            facing_right=self.facing_right,
            animation_timer=self.animation_timer,
        )
        # Apply alpha for respawn fade effect
        self.image.set_alpha(round(self.alpha))
