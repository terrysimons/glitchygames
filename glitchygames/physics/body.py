"""PhysicsBody: composable force/behavior accumulator.

The core of the physics engine. A PhysicsBody holds position, velocity,
and mass, and is driven by a list of composable behaviors (forces) and
constraints (hard limits). Each tick:

1. Behaviors compute forces → summed into net_force
2. net_force / mass → acceleration → velocity → position
3. Constraints clamp position and set flags (on_ground, etc.)

Convenience presets create pre-configured bodies for common game types.
"""

from __future__ import annotations

from typing import Any

from glitchygames.physics.behaviors import (
    AccelerationBehavior,
    FrictionBehavior,
    GravityBehavior,
    PhysicsBehavior,
)
from glitchygames.physics.constraints import (
    BoundsConstraint,
    GroundConstraint,
    PhysicsConstraint,
)


class PhysicsBody:
    """Composable physics body with behaviors and constraints.

    Stores position, velocity, and mass. Behaviors contribute forces
    each tick; constraints enforce hard limits after integration.

    Args:
        world_x: Initial X position in world space.
        world_y: Initial Y position in world space.
        mass: Body mass (affects force → acceleration conversion).
        behaviors: Initial list of physics behaviors.
        constraints: Initial list of physics constraints.

    """

    def __init__(
        self,
        world_x: float = 0.0,
        world_y: float = 0.0,
        mass: float = 1.0,
        behaviors: list[PhysicsBehavior] | None = None,
        constraints: list[PhysicsConstraint] | None = None,
    ) -> None:
        """Initialize the physics body."""
        self.world_x = world_x
        self.world_y = world_y
        self.velocity_x: float = 0.0
        self.velocity_y: float = 0.0
        self.mass = mass

        # Composable behaviors and constraints
        self.behaviors: list[PhysicsBehavior] = list(behaviors) if behaviors else []
        self.constraints: list[PhysicsConstraint] = list(constraints) if constraints else []

        # State flags (set by constraints, read by animation/AI)
        self.on_ground: bool = False
        self.facing_right: bool = True

    def tick(self, dt: float) -> None:
        """Advance physics by one frame.

        1. Sum forces from all behaviors.
        2. Apply net force as acceleration (F = ma).
        3. Integrate velocity into position.
        4. Apply constraints.

        Args:
            dt: Delta time in seconds since last frame.

        """
        # Accumulate forces from all behaviors
        net_force_x = 0.0
        net_force_y = 0.0
        for behavior in self.behaviors:
            force_x, force_y = behavior.compute_force(self, dt)
            net_force_x += force_x
            net_force_y += force_y

        # F = ma → a = F/m → v += a * dt
        if self.mass > 0:
            self.velocity_x += (net_force_x / self.mass) * dt
            self.velocity_y += (net_force_y / self.mass) * dt

        # Integrate velocity → position
        self.world_x += self.velocity_x * dt
        self.world_y += self.velocity_y * dt

        # Update facing direction from velocity
        if self.velocity_x > 0:
            self.facing_right = True
        elif self.velocity_x < 0:
            self.facing_right = False

        # Apply constraints (bounds, ground, etc.)
        for constraint in self.constraints:
            constraint.apply(self, dt)

    def add_behavior(self, behavior: PhysicsBehavior) -> None:
        """Add a composable behavior to this body.

        Args:
            behavior: The behavior to add.

        """
        self.behaviors.append(behavior)

    def remove_behavior(self, behavior: PhysicsBehavior) -> None:
        """Remove a behavior from this body.

        Args:
            behavior: The behavior to remove.

        """
        self.behaviors.remove(behavior)

    def get_behavior(self, behavior_type: type[Any]) -> Any | None:
        """Find the first behavior of a given type.

        Args:
            behavior_type: The class to search for.

        Returns:
            The first matching behavior, or None.

        """
        for behavior in self.behaviors:
            if isinstance(behavior, behavior_type):
                return behavior
        return None

    def add_constraint(self, constraint: PhysicsConstraint) -> None:
        """Add a constraint to this body.

        Args:
            constraint: The constraint to add.

        """
        self.constraints.append(constraint)

    # --- Convenience presets ---

    @classmethod
    def platformer(
        cls,
        world_x: float = 0.0,
        world_y: float = 0.0,
        gravity: float = 1200.0,
        terminal_velocity: float = 800.0,
        acceleration: float = 1600.0,
        deceleration: float = 1200.0,
        ground_y: float = 400.0,
        body_height: float = 48.0,
    ) -> PhysicsBody:
        """Create a platformer character physics body.

        Pre-configured with gravity, acceleration/deceleration curves,
        and ground constraint.

        Args:
            world_x: Initial X position.
            world_y: Initial Y position.
            gravity: Downward acceleration (pixels/sec^2).
            terminal_velocity: Max fall speed (pixels/sec).
            acceleration: Horizontal acceleration rate (pixels/sec^2).
            deceleration: Horizontal deceleration rate (pixels/sec^2).
            ground_y: Y coordinate of the ground surface.
            body_height: Height of the character for ground detection.

        Returns:
            A configured PhysicsBody.

        """
        return cls(
            world_x=world_x,
            world_y=world_y,
            behaviors=[
                GravityBehavior(
                    strength=gravity,
                    terminal_velocity=terminal_velocity,
                ),
                AccelerationBehavior(
                    acceleration=acceleration,
                    deceleration=deceleration,
                ),
            ],
            constraints=[
                BoundsConstraint(min_x=0.0),
                GroundConstraint(
                    ground_y=ground_y,
                    body_height=body_height,
                ),
            ],
        )

    @classmethod
    def top_down(
        cls,
        world_x: float = 0.0,
        world_y: float = 0.0,
        friction: float = 0.1,
    ) -> PhysicsBody:
        """Create a top-down character physics body.

        Pre-configured with friction for smooth deceleration.
        No gravity.

        Args:
            world_x: Initial X position.
            world_y: Initial Y position.
            friction: Friction coefficient (0.0 to 1.0).

        Returns:
            A configured PhysicsBody.

        """
        return cls(
            world_x=world_x,
            world_y=world_y,
            behaviors=[
                FrictionBehavior(coefficient=friction),
            ],
        )

    @classmethod
    def static(
        cls,
        world_x: float = 0.0,
        world_y: float = 0.0,
    ) -> PhysicsBody:
        """Create a static (non-moving) physics body.

        No behaviors or constraints. Position never changes.

        Args:
            world_x: X position.
            world_y: Y position.

        Returns:
            A configured PhysicsBody with no physics.

        """
        return cls(world_x=world_x, world_y=world_y)
