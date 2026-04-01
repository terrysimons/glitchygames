"""Player sprite with platformer physics for Brave Adventurer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, override

import pygame

# GRAVITY, MAX_FALL_SPEED, PLAYER_ACCELERATION, PLAYER_DECELERATION used in PhysicsBody.platformer()
from glitchygames.animation.expressions import Expression
from glitchygames.examples.brave_adventurer.constants import (
    FALLING_VELOCITY_THRESHOLD,
    GRAVITY,
    JUMP_VELOCITY,
    LAYER_PLAYER,
    MAX_FALL_SPEED,
    PLAYER_ACCELERATION,
    PLAYER_DECELERATION,
    PLAYER_HEIGHT,
    PLAYER_RUN_SPEED,
    PLAYER_WIDTH,
    STARTING_LIVES,
)
from glitchygames.examples.brave_adventurer.drawing import draw_player
from glitchygames.physics import (
    AccelerationBehavior,
    BoundsConstraint,
    GravityBehavior,
    PhysicsBody,
)
from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from glitchygames.camera import Camera2D


class _FallingCondition(Expression):
    """Custom compound condition: velocity_y > threshold AND NOT on_ground.

    Phase 1 expression parser doesn't support 'and'/'not' yet.
    """

    @override
    def evaluate(self, context: dict[str, Any]) -> bool:
        """Check if the player is falling.

        Returns:
            True if velocity_y exceeds threshold and not on ground.

        """
        return context.get('velocity_y', 0.0) > FALLING_VELOCITY_THRESHOLD and not context.get(
            'on_ground', True
        )


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

        # Animation state machine (code-defined since primitives don't use TOML)
        from glitchygames.animation import AnimationStateMachine

        self.state: str = self.IDLE
        self.animation_timer: float = 0.0
        self.state_machine = AnimationStateMachine(self)
        self.state_machine.add_transition('idle', 'running', when='abs(velocity_x) > 0.1')
        self.state_machine.add_transition('running', 'idle', when='abs(velocity_x) <= 0.1')
        self.state_machine.add_transition('idle', 'jumping', when='velocity_y < -10.0')
        self.state_machine.add_transition('running', 'jumping', when='velocity_y < -10.0')
        self.state_machine.add_transition('falling', 'idle', when='on_ground')
        self.state_machine.add_transition('jumping', 'idle', when='on_ground')
        # Falling condition is compound (needs Phase 2 parser for "and not")
        falling_condition = _FallingCondition()
        self.state_machine.add_transition('idle', 'falling', condition=falling_condition)
        self.state_machine.add_transition('jumping', 'falling', condition=falling_condition)
        self.state_machine.set_state(self.IDLE)

        # Game state
        self.lives: int = STARTING_LIVES
        self.score: int = 0
        self.max_distance: float = 0.0

        # Visual effects
        self.alpha: float = 255.0
        self.is_respawning: bool = False

        # Always redraw (position changes every frame due to camera)
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

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Advance physics and update animation state.

        Args:
            dt: Delta time in seconds since the last frame.

        """
        super().dt_tick(dt)
        self.animation_timer += dt

        # PhysicsBody handles gravity, acceleration, bounds, integration
        self.physics.tick(dt)

        # State machine evaluates transitions from code-defined rules
        context = self.physics.get_animation_context()
        self.state_machine.evaluate(context, dt)
        self.state = self.state_machine.current_state

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
