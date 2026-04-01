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

# GRAVITY, MAX_FALL_SPEED, PLAYER_ACCELERATION, PLAYER_DECELERATION used in PhysicsBody.platformer()
from glitchygames.examples.brave_adventurer_papyrus.sprite_utils import (
    apply_transparency_and_scale,
    prepare_papyrus_sprite,
)
from glitchygames.physics import (
    AccelerationBehavior,
    BoundsConstraint,
    GravityBehavior,
    PhysicsBody,
)
from glitchygames.sprites import AnimatedSprite

if TYPE_CHECKING:
    from glitchygames.camera import Camera2D


class PapyrusPlayer(AnimatedSprite):
    """Adventurer character using TOML sprite animations with platformer physics.

    Extends AnimatedSprite for TOML rendering. Physics is delegated to a
    composed PhysicsBody instance.
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

        # Physics body handles position, velocity, gravity, acceleration, bounds.
        # Ground collision is handled by game.py (terrain-based), not by a
        # GroundConstraint, so we build the body manually without one.
        self.physics: PhysicsBody = PhysicsBody(
            world_x=world_x,
            world_y=world_y,
            behaviors=[
                GravityBehavior(
                    strength=GRAVITY,
                    terminal_velocity=MAX_FALL_SPEED,
                ),
                AccelerationBehavior(
                    acceleration=PLAYER_ACCELERATION,
                    deceleration=PLAYER_DECELERATION,
                ),
            ],
            constraints=[
                BoundsConstraint(min_x=0.0),
            ],
        )

        self.rect.x = round(world_x)
        self.rect.y = round(world_y)

        # Animation state
        self.state: str = self.IDLE

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

    # --- Property delegates to PhysicsBody ---

    @property
    def world_x(self) -> float:
        """X position in world space."""
        return self.physics.world_x

    @world_x.setter
    def world_x(self, value: float) -> None:
        self.physics.world_x = value

    @property
    def world_y(self) -> float:
        """Y position in world space."""
        return self.physics.world_y

    @world_y.setter
    def world_y(self, value: float) -> None:
        self.physics.world_y = value

    @property
    def velocity_x(self) -> float:
        """Horizontal velocity in pixels/sec."""
        return self.physics.velocity_x

    @velocity_x.setter
    def velocity_x(self, value: float) -> None:
        self.physics.velocity_x = value

    @property
    def velocity_y(self) -> float:
        """Vertical velocity in pixels/sec."""
        return self.physics.velocity_y

    @velocity_y.setter
    def velocity_y(self, value: float) -> None:
        self.physics.velocity_y = value

    @property
    def on_ground(self) -> bool:
        """Whether the player is on the ground."""
        return self.physics.on_ground

    @on_ground.setter
    def on_ground(self, value: bool) -> None:
        self.physics.on_ground = value

    @property
    def facing_right(self) -> bool:
        """Whether the player faces right."""
        return self.physics.facing_right

    @facing_right.setter
    def facing_right(self, value: bool) -> None:
        self.physics.facing_right = value

    # --- Physics ---

    def dt_tick(self: Self, dt: float) -> None:
        """Advance physics, animation, and detect state changes.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        self.dt = dt
        self.dt_timer += dt

        # PhysicsBody handles gravity, acceleration, bounds, integration
        self.physics.tick(dt)

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
        accel = self.physics.get_behavior(AccelerationBehavior)
        if accel:
            accel.target_velocity_x = PLAYER_RUN_SPEED
        self.facing_right = True

    def move_left(self) -> None:
        """Start moving left with smooth acceleration."""
        accel = self.physics.get_behavior(AccelerationBehavior)
        if accel:
            accel.target_velocity_x = -PLAYER_RUN_SPEED
        self.facing_right = False

    def stop_horizontal(self) -> None:
        """Smoothly decelerate to a stop."""
        accel = self.physics.get_behavior(AccelerationBehavior)
        if accel:
            accel.target_velocity_x = 0.0

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
