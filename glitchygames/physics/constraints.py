"""Physics constraints that modify position/velocity after integration.

Constraints run AFTER force accumulation and velocity integration.
They enforce hard limits like world boundaries, attachment points,
and collision resolution.

All constraints implement the PhysicsConstraint protocol:
    apply(body, dt) -> None
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from glitchygames.physics.body import PhysicsBody


@runtime_checkable
class PhysicsConstraint(Protocol):
    """Protocol for physics constraints applied after integration."""

    def apply(self, body: PhysicsBody, dt: float) -> None:
        """Apply this constraint to the body.

        Args:
            body: The physics body to constrain.
            dt: Delta time in seconds.

        """
        ...


class BoundsConstraint:
    """Clamp position within world boundaries.

    Prevents the body from moving outside the configured bounds.
    When a boundary is hit, position is clamped and the corresponding
    velocity component is zeroed.

    Args:
        min_x: Left boundary (None = unbounded).
        min_y: Top boundary (None = unbounded).
        max_x: Right boundary (None = unbounded).
        max_y: Bottom boundary (None = unbounded).

    """

    def __init__(
        self,
        *,
        min_x: float | None = None,
        min_y: float | None = None,
        max_x: float | None = None,
        max_y: float | None = None,
    ) -> None:
        """Initialize bounds constraint."""
        self.min_x = min_x
        self.min_y = min_y
        self.max_x = max_x
        self.max_y = max_y

    def apply(self, body: PhysicsBody, dt: float) -> None:  # noqa: ARG002
        """Clamp body position to bounds, zeroing velocity at boundaries.

        Args:
            body: The physics body to constrain.
            dt: Delta time (unused, required by protocol).

        """
        if self.min_x is not None and body.world_x < self.min_x:
            body.world_x = self.min_x
            body.velocity_x = 0.0

        if self.max_x is not None and body.world_x > self.max_x:
            body.world_x = self.max_x
            body.velocity_x = 0.0

        if self.min_y is not None and body.world_y < self.min_y:
            body.world_y = self.min_y
            body.velocity_y = 0.0

        if self.max_y is not None and body.world_y > self.max_y:
            body.world_y = self.max_y
            body.velocity_y = 0.0


class GroundConstraint:
    """Keep body on or above a ground level.

    When the body's bottom edge touches or passes through the ground,
    position is snapped to the ground and on_ground is set to True.
    Sets on_ground to False when the body is above the ground.

    Args:
        ground_y: The Y coordinate of the ground surface.
        body_height: The height of the body (used to calculate bottom edge).

    """

    def __init__(self, ground_y: float, body_height: float) -> None:
        """Initialize ground constraint."""
        self.ground_y = ground_y
        self.body_height = body_height

    def apply(self, body: PhysicsBody, dt: float) -> None:  # noqa: ARG002
        """Snap body to ground when touching, set on_ground flag.

        Args:
            body: The physics body to constrain.
            dt: Delta time (unused, required by protocol).

        """
        body_bottom = body.world_y + self.body_height

        if body_bottom >= self.ground_y and body.velocity_y >= 0:
            body.world_y = self.ground_y - self.body_height
            body.velocity_y = 0.0
            if hasattr(body, 'on_ground'):
                body.on_ground = True
        elif hasattr(body, 'on_ground'):
            body.on_ground = False
