"""Papyrus Edition player sprite using TOML animation system."""

from __future__ import annotations

from typing import Any, Self, override

import pygame

# GRAVITY, MAX_FALL_SPEED, PLAYER_ACCELERATION, PLAYER_DECELERATION used in PhysicsBody.platformer()
from glitchygames.collision.layers import collision_rect_offset
from glitchygames.examples.brave_adventurer_papyrus.constants import (
    GRAVITY,
    JUMP_VELOCITY,
    LAYER_PLAYER,
    MAX_FALL_SPEED,
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
from glitchygames.physics import (
    AccelerationBehavior,
    BoundsConstraint,
    GravityBehavior,
    PhysicsBody,
)
from glitchygames.sprites import AnimatedSprite, FrameAnchor
from glitchygames.world import CoordinateSpace


class PapyrusPlayer(AnimatedSprite):
    """Adventurer character using TOML sprite animations with platformer physics.

    Extends AnimatedSprite for TOML rendering. Physics is delegated to a
    composed PhysicsBody instance. A world sprite: the engine places its screen
    rect from the camera each frame, adding the anchored frame's draw_offset.
    """

    COORDINATE_SPACE = CoordinateSpace.WORLD

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
        # Frames are top-aligned with visible bottoms from 24 to 27 rows; anchor them at the
        # hitbox bottom so the feet always sit on the 27-row foot line PAPYRUS_PLAYER_HEIGHT
        # stands on (the engine adds the per-frame draw_offset when it places rect)
        self.frame_anchor = FrameAnchor.BOTTOM

        # Physics body handles position, velocity, gravity, acceleration, bounds.
        # Ground collision is handled by game.py (terrain-based), not by a
        # GroundConstraint, so we build the body manually without one.
        # World left edge: refitted to the hitbox every tick (see _fit_world_edge_to_hitbox)
        self._world_edge_bounds = BoundsConstraint(min_x=0.0)
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
            constraints=[self._world_edge_bounds],
        )

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

        # State machine is auto-loaded from TOML [[transition]] sections
        # (including the falling transitions; see sprites/player.toml).
        if self.state_machine is not None:
            self.state_machine.set_state(self.IDLE)

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

    def _fit_world_edge_to_hitbox(self: Self) -> None:
        """Let the hitbox, not the image's transparent margin, stop at the world's left edge.

        The margin changes with the animation frame's hitbox, so the bound is refitted from
        the current collision rect each tick.
        """
        offset_x, _ = collision_rect_offset(self)
        self._world_edge_bounds.min_x = float(-offset_x)

    def dt_tick(self: Self, dt: float) -> None:
        """Advance physics, animation, and detect state changes.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        self.dt = dt
        self.dt_timer += dt

        # PhysicsBody handles gravity, acceleration, bounds, integration
        self._fit_world_edge_to_hitbox()
        self.physics.tick(dt)

        # State machine evaluates transitions from TOML + code overrides
        if self.state_machine is not None:
            context = self.physics.get_animation_context()
            self.state_machine.evaluate(context, dt)

        # Advance TOML animation frames and fix transparency
        AnimatedSprite.update(self, dt)
        apply_transparency_and_scale(self)

        # Flip image when facing left, and mirror the hitbox with it
        self.hitbox_flip_x = not self.facing_right
        if not self.facing_right:
            self.image = pygame.transform.flip(self.image, flip_x=True, flip_y=False)

        # The frame and facing may have changed the hitbox's offset since physics clamped
        # against the world edge, so refit and clamp again with the hitbox now drawn
        self._fit_world_edge_to_hitbox()
        self._world_edge_bounds.apply(self.physics, dt)

        # Apply alpha for respawn fade effect
        self.image.set_alpha(round(self.alpha))

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

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """No-op. Animation is advanced in dt_tick() instead."""
