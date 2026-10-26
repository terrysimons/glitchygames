"""Player sprite with platformer physics for Brave Adventurer."""

from __future__ import annotations

from typing import Self, override

import pygame

from brave_adventurer.constants import (
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
from brave_adventurer.drawing import draw_player
from glitchygames.collision.bounds import opaque_bounds
from glitchygames.collision.layers import collision_rect_offset
from glitchygames.physics import (
    AccelerationBehavior,
    BoundsConstraint,
    GravityBehavior,
    PhysicsBody,
)
from glitchygames.sprites import Sprite
from glitchygames.world import CoordinateSpace

# Common (every-pose) hitbox x-range per facing, measured once; see common_hitbox_x_range
_COMMON_POSE_X_RANGES: dict[bool, tuple[int, int]] = {}
# Animation times sampled when measuring poses (two seconds at 50 ms covers every cycle)
_POSE_SAMPLE_TIMES = tuple(sample_index * 0.05 for sample_index in range(40))


def _measure_common_pose_x_range(*, facing_right: bool) -> tuple[int, int]:
    """Draw every pose for one facing and intersect their visible-pixel x-ranges.

    Returns:
        tuple[int, int]: (left, right) of the columns every pose covers; right exclusive.

    """
    scratch = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT), pygame.SRCALPHA)
    common_left = 0
    common_right = PLAYER_WIDTH
    for state in (Player.IDLE, Player.RUNNING, Player.JUMPING, Player.FALLING):
        for animation_time in _POSE_SAMPLE_TIMES:
            scratch.fill((0, 0, 0, 0))
            draw_player(scratch, state, facing_right=facing_right, animation_timer=animation_time)
            visible = opaque_bounds(scratch)
            common_left = max(common_left, visible.left)
            common_right = min(common_right, visible.right)
    return (common_left, common_right)


class Player(Sprite):
    """The adventurer character with platformer physics.

    Stores world-space coordinates separately from the screen-space rect.
    Physics (gravity, jumping) and the pose are applied in dt_tick(). A world
    sprite: the engine places its screen rect from the camera each frame.
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
        # World left edge: refitted to the hitbox every tick (see _fit_world_edge_to_hitbox)
        self._world_edge_bounds = BoundsConstraint(min_x=0.0)
        # Kept so the move methods set its target directly (the body always has it)
        self._acceleration_behavior = AccelerationBehavior(
            acceleration=PLAYER_ACCELERATION,
            deceleration=PLAYER_DECELERATION,
        )
        self.physics: PhysicsBody = PhysicsBody(
            world_x=world_x,
            world_y=world_y,
            behaviors=[
                GravityBehavior(
                    strength=GRAVITY,
                    terminal_velocity=MAX_FALL_SPEED,
                ),
                self._acceleration_behavior,
            ],
            constraints=[self._world_edge_bounds],
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
        falling_when = f'velocity_y > {FALLING_VELOCITY_THRESHOLD} and not on_ground'
        self.state_machine.add_transition('idle', 'falling', when=falling_when)
        self.state_machine.add_transition('jumping', 'falling', when=falling_when)
        # Running off a ledge falls (evaluated after running's own rules, as idle's is)
        self.state_machine.add_transition('running', 'falling', when=falling_when)
        self.state_machine.set_state(self.IDLE)

        # Game state
        self.lives: int = STARTING_LIVES
        self.score: int = 0
        # Gold scarab bonuses collected; the score is the distance score plus these
        self.bonus_points: int = 0
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

    def common_hitbox_x_range(self: Self) -> tuple[int, int]:
        """Return the horizontal hitbox span shared by every pose, for the current facing.

        Poses are drawn procedurally and differ in width (falling is wider than idle), so
        support (ledges, wall tops) uses the columns every pose covers: otherwise an idle
        player at an edge would fall, be caught by the wider falling pose, land, and repeat.
        Measured once per facing by drawing every state over a range of animation times.

        Returns:
            tuple[int, int]: (left, right) offsets from the drawn position; right exclusive.

        """
        cached_range = _COMMON_POSE_X_RANGES.get(self.facing_right)
        if cached_range is None:
            cached_range = _measure_common_pose_x_range(facing_right=self.facing_right)
            _COMMON_POSE_X_RANGES[self.facing_right] = cached_range
        return cached_range

    def _fit_world_edge_to_hitbox(self: Self) -> None:
        """Let the hitbox, not the image's transparent margin, stop at the world's left edge.

        The margin changes with pose, facing and animation frame, so the bound is refitted
        from the current collision rect each tick.
        """
        offset_x, _ = collision_rect_offset(self)
        self._world_edge_bounds.min_x = float(-offset_x)

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Advance physics and update animation state, then draw this frame's pose.

        The pose is drawn here, not in update(), because the hitbox is trimmed to the drawn
        pixels: collision (the world edge here, the scene's ground and wall checks after this)
        must use this frame's pose, not the previous frame's (the pose-before-collision rule,
        plans/2026-10-18-engine-world-space.md section 1).

        Args:
            dt: Delta time in seconds since the last frame.

        """
        super().dt_tick(dt)
        self.animation_timer += dt

        # PhysicsBody handles gravity, acceleration, bounds, integration
        self._fit_world_edge_to_hitbox()
        self.physics.tick(dt)

        # State machine evaluates transitions from code-defined rules
        context = self.physics.get_animation_context()
        self.state_machine.evaluate(context, dt)
        self.state = self.state_machine.current_state

        self._draw_pose()
        # The new pose (facing or state) can move the hitbox inside the image, so the world
        # edge is refitted to it and applied again: the hitbox never passes the left edge
        self._fit_world_edge_to_hitbox()
        self._world_edge_bounds.apply(self.physics, dt)

    def _draw_pose(self: Self) -> None:
        """Redraw the image for the current state, facing and animation time."""
        self.image.fill((0, 0, 0, 0))
        draw_player(
            self.image,
            self.state,
            facing_right=self.facing_right,
            animation_timer=self.animation_timer,
        )

    def jump(self) -> None:
        """Initiate a jump if the player is on the ground."""
        if self.on_ground:
            self.velocity_y = JUMP_VELOCITY
            self.on_ground = False

    def move_right(self) -> None:
        """Start moving right with smooth acceleration."""
        self._acceleration_behavior.target_velocity_x = PLAYER_RUN_SPEED
        self.facing_right = True

    def move_left(self) -> None:
        """Start moving left with smooth acceleration."""
        self._acceleration_behavior.target_velocity_x = -PLAYER_RUN_SPEED
        self.facing_right = False

    def stop_horizontal(self) -> None:
        """Smoothly decelerate to a stop."""
        self._acceleration_behavior.target_velocity_x = 0.0

    @override
    def update(self: Self) -> None:
        """Apply the respawn fade (purely visual; the pose is drawn in dt_tick)."""
        self.image.set_alpha(round(self.alpha))
