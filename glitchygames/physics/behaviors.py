"""Composable physics behaviors for the force/behavior accumulator.

Each behavior computes a force contribution that gets summed into the
net force on a PhysicsBody. Behaviors are additive and composable --
stack GravityBehavior + BuoyancyBehavior + WindBehavior on the same
object for emergent physics.

All behaviors implement the PhysicsBehavior protocol:
    compute_force(body, dt) -> tuple[float, float]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from glitchygames.physics.body import PhysicsBody


@runtime_checkable
class PhysicsBehavior(Protocol):
    """Protocol for composable physics behaviors."""

    def compute_force(self, body: PhysicsBody, dt: float) -> tuple[float, float]:
        """Compute the force this behavior contributes.

        Args:
            body: The physics body this behavior is attached to.
            dt: Delta time in seconds.

        Returns:
            Force as (force_x, force_y) in pixels/sec^2 * mass.

        """
        ...


class GravityBehavior:
    """Constant downward force simulating gravity.

    Applies a downward acceleration capped at a terminal velocity.
    In pygame coordinates, positive Y is downward.

    Args:
        strength: Gravitational acceleration in pixels/sec^2.
        terminal_velocity: Maximum downward speed in pixels/sec.
            Set to 0.0 for no terminal velocity cap.

    """

    def __init__(
        self,
        strength: float = 1200.0,
        terminal_velocity: float = 800.0,
    ) -> None:
        """Initialize gravity behavior."""
        self.strength = strength
        self.terminal_velocity = terminal_velocity

    def compute_force(self, body: PhysicsBody, dt: float) -> tuple[float, float]:
        """Apply downward gravitational force, respecting terminal velocity.

        Returns:
            Force as (0, gravity * mass), capped at terminal velocity.

        """
        if self.terminal_velocity > 0.0 and body.velocity_y >= self.terminal_velocity:
            # Already at terminal velocity -- no additional force
            return (0.0, 0.0)

        if body.mass <= 0.0:
            return (0.0, 0.0)

        force_y = self.strength * body.mass

        # Predict if this force would exceed terminal velocity
        if self.terminal_velocity > 0.0:
            predicted_velocity_y = body.velocity_y + (force_y / body.mass) * dt
            if predicted_velocity_y > self.terminal_velocity:
                # Scale force to reach exactly terminal velocity
                needed_acceleration = (self.terminal_velocity - body.velocity_y) / dt
                force_y = needed_acceleration * body.mass

        return (0.0, force_y)


class AccelerationBehavior:
    """Smooth acceleration toward a target velocity.

    Ramps the body's horizontal velocity toward a target using
    configurable acceleration and deceleration rates. Promoted
    from brave_adventurer/player.py's _ramp_velocity() function.

    Args:
        acceleration: Rate when moving toward nonzero target (pixels/sec^2).
        deceleration: Rate when slowing to zero (pixels/sec^2).

    """

    def __init__(
        self,
        acceleration: float = 1600.0,
        deceleration: float = 1200.0,
    ) -> None:
        """Initialize acceleration behavior."""
        self.acceleration = acceleration
        self.deceleration = deceleration
        self.target_velocity_x: float = 0.0

    def compute_force(self, body: PhysicsBody, dt: float) -> tuple[float, float]:
        """Compute horizontal acceleration force toward target velocity.

        This behavior directly modifies velocity rather than returning a
        force, because acceleration/deceleration curves aren't easily
        expressed as constant forces. The returned force is (0, 0) since
        the velocity change is applied directly.

        Returns:
            Always (0, 0) -- velocity is modified directly on the body.

        """
        new_velocity_x = _ramp_velocity(
            current=body.velocity_x,
            target=self.target_velocity_x,
            acceleration=self.acceleration,
            deceleration=self.deceleration,
            dt=dt,
        )
        # Apply directly to body (not via force accumulation)
        body.velocity_x = new_velocity_x
        return (0.0, 0.0)


class FrictionBehavior:
    """Velocity damping that simulates friction or air resistance.

    Reduces velocity each frame by multiplying by (1 - coefficient).
    A coefficient of 0.0 means no friction; 1.0 means instant stop.

    Args:
        coefficient: Friction coefficient (0.0 to 1.0).

    """

    def __init__(self, coefficient: float = 0.1) -> None:
        """Initialize friction behavior."""
        self.coefficient = coefficient

    def compute_force(self, body: PhysicsBody, dt: float) -> tuple[float, float]:  # noqa: ARG002
        """Apply friction by scaling velocity toward zero.

        Like AccelerationBehavior, this modifies velocity directly
        rather than returning a force.

        Returns:
            Always (0, 0) -- velocity is modified directly.

        """
        damping = 1.0 - self.coefficient
        body.velocity_x *= damping
        body.velocity_y *= damping
        return (0.0, 0.0)


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
