"""The Tinker — player character for Clockwork Keep."""

from __future__ import annotations

from typing import Any, Self, override

import pygame

from clockwork_keep.constants import (
    FALLING_VELOCITY_THRESHOLD,
    GRAVITY,
    JUMP_VELOCITY,
    JUMP_VELOCITY_RUNNING,
    LAYER_PLAYER,
    MAX_FALL_SPEED,
    PLAYER_ACCELERATION,
    PLAYER_DECELERATION,
    PLAYER_HEIGHT,
    PLAYER_RUN_SPEED,
    PLAYER_WALK_SPEED,
    PLAYER_WIDTH,
    PLAYFIELD_LEFT,
    PLAYFIELD_RIGHT,
    STARTING_LIVES,
)
from clockwork_keep.drawing import draw_tinker
from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.physics import (
    AccelerationBehavior,
    BoundsConstraint,
    GravityBehavior,
    PhysicsBody,
)
from glitchygames.sprites import Sprite
from glitchygames.world import CoordinateSpace


class Tinker(Sprite):
    """The Tinker — a goggled mechanic exploring the clockwork tower.

    Uses PhysicsBody for platformer movement and an animation state
    machine for visual states. A world sprite: the engine places it from the camera.
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
        """Initialize the Tinker.

        Args:
            world_x: Starting X in world coordinates.
            world_y: Starting Y in world coordinates.
            groups: Sprite group to add to.

        """
        self._layer = LAYER_PLAYER

        super().__init__(
            x=world_x,
            y=world_y,
            width=PLAYER_WIDTH,
            height=PLAYER_HEIGHT,
            name='Tinker',
            groups=groups,
        )

        self.image = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT), pygame.SRCALPHA)

        # Side walls: refitted to the hitbox every tick (see _fit_playfield_bounds_to_hitbox)
        self._playfield_bounds = BoundsConstraint(
            min_x=float(PLAYFIELD_LEFT),
            max_x=float(PLAYFIELD_RIGHT - PLAYER_WIDTH),
        )
        # Kept so the move methods set its target directly (the body always has it)
        self._acceleration_behavior = AccelerationBehavior(
            acceleration=PLAYER_ACCELERATION,
            deceleration=PLAYER_DECELERATION,
        )
        self.physics: PhysicsBody = PhysicsBody(
            world_x=world_x,
            world_y=world_y,
            behaviors=[
                GravityBehavior(strength=GRAVITY, terminal_velocity=MAX_FALL_SPEED),
                self._acceleration_behavior,
            ],
            constraints=[self._playfield_bounds],
        )

        # Animation state machine
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
        falling_when = f'velocity_y > {FALLING_VELOCITY_THRESHOLD} and not on_ground'
        self.state_machine.add_transition('idle', 'falling', when=falling_when)
        self.state_machine.add_transition('jumping', 'falling', when=falling_when)
        self.state_machine.set_state(self.IDLE)

        # Game state
        self.lives: int = STARTING_LIVES
        self.score: int = 0
        self.floor: int = 0

        # Visual effects
        self.alpha: float = 255.0
        self.is_respawning: bool = False

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
        """Horizontal velocity."""
        return self.physics.velocity_x

    @velocity_x.setter
    def velocity_x(self, value: float) -> None:
        self.physics.velocity_x = value

    @property
    def velocity_y(self) -> float:
        """Vertical velocity."""
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
        """Advance physics and animation, then draw this frame's pose.

        The pose is drawn here, not in update(), because the hitbox is trimmed to the drawn
        pixels: collision (the side walls here, the floor's ground and cog checks after this)
        must use this frame's pose, not the previous frame's (the pose-before-collision rule,
        plans/2026-10-18-engine-world-space.md section 1).

        Args:
            dt: Delta time in seconds.

        """
        super().dt_tick(dt)
        self.animation_timer += dt
        self._fit_playfield_bounds_to_hitbox()
        self.physics.tick(dt)

        context = self.physics.get_animation_context()
        self.state_machine.evaluate(context, dt)
        self.state = self.state_machine.current_state

        self._draw_pose()
        # The new pose (facing or state) can move the hitbox inside the image, so the side
        # walls are refitted to it and applied again: the hitbox never enters a wall
        self._fit_playfield_bounds_to_hitbox()
        self._playfield_bounds.apply(self.physics, dt)

    def _draw_pose(self: Self) -> None:
        """Redraw the image for the current state, facing and animation time."""
        self.image.fill((0, 0, 0, 0))
        draw_tinker(
            self.image,
            self.state,
            facing_right=self.facing_right,
            animation_timer=self.animation_timer,
        )

    def _fit_playfield_bounds_to_hitbox(self: Self) -> None:
        """Set the side-wall bounds so the hitbox, not the whole image, meets the walls.

        The figure's transparent margin moves with its pose and facing (4 px on the side it
        faces away from), so the bounds are refitted from the current collision rect each
        tick: its left edge stops at PLAYFIELD_LEFT and its right edge at PLAYFIELD_RIGHT.
        """
        hitbox = get_sprite_collision_rect(self)
        offset_x, _ = collision_rect_offset(self)
        self._playfield_bounds.min_x = float(PLAYFIELD_LEFT - offset_x)
        self._playfield_bounds.max_x = float(PLAYFIELD_RIGHT - (offset_x + hitbox.width))

    def jump(self, *, running: bool = False) -> None:
        """Initiate a jump if on the ground.

        Args:
            running: If True, use the higher running jump velocity.

        """
        if self.on_ground:
            self.velocity_y = JUMP_VELOCITY_RUNNING if running else JUMP_VELOCITY
            self.on_ground = False

    def move_right(self, *, running: bool = False) -> None:
        """Start moving right.

        Args:
            running: If True, use run speed instead of walk speed.

        """
        speed = PLAYER_RUN_SPEED if running else PLAYER_WALK_SPEED
        self._acceleration_behavior.target_velocity_x = speed
        self.facing_right = True

    def move_left(self, *, running: bool = False) -> None:
        """Start moving left.

        Args:
            running: If True, use run speed instead of walk speed.

        """
        speed = PLAYER_RUN_SPEED if running else PLAYER_WALK_SPEED
        self._acceleration_behavior.target_velocity_x = -speed
        self.facing_right = False

    def stop_horizontal(self) -> None:
        """Decelerate to a stop."""
        self._acceleration_behavior.target_velocity_x = 0.0

    @override
    def update(self: Self) -> None:
        """Apply the respawn fade (purely visual; the pose is drawn in dt_tick)."""
        self.image.set_alpha(round(self.alpha))
