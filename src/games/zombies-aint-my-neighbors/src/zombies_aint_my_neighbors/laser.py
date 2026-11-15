"""The laser pointer: its battery, and the dot its light makes on the lawn.

Feature plan 8 (plans/2026-11-15-zombies-aint-my-neighbors-8-laser-pointer.md). The battery
gives 3 s of shine when full: shining drains it 1 s a second, and not shining (whichever weapon
the kid holds) refills it at 0.3 s a second, 10 s from empty. Run flat, it is dead until it has
refilled to 1.0 s, so it can't flicker on and off at empty. The order within a frame: a battery
in use drains (and dies on reaching empty); a resting one refills (and wakes on reaching 1.0 s).
The light itself waits ``WARM_UP_SECONDS`` of drawing before it shows (the kid counts it), so a
tapped trigger spends charge and never lights (the owner, 2026-11-15).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Self, override

from glitchygames.sprites import AnimatedSprite
from glitchygames.world import CoordinateSpace
from zombies_aint_my_neighbors.tolerances import TIME_TOLERANCE

if TYPE_CHECKING:
    import pygame

# Feature plan 8
FULL_SECONDS: Final = 3.0
RECHARGE_PER_SECOND: Final = 0.3
REVIVE_SECONDS: Final = 1.0
# The owner, 2026-11-15: a delay before the laser shows, the battery drawing through it, against
# rapid fire and for tension
WARM_UP_SECONDS: Final = 0.4
# The dot lands this far ahead of the kid's feet, along its aim
DOT_DISTANCE: Final = 160.0
DOT_SIZE: Final = 8
DOT_FILE: Final = Path(__file__).resolve().parent / 'sprites' / 'laser_dot.toml'


class LaserBattery:
    """One kid's laser battery: charge in seconds of shine, and whether it has died."""

    def __init__(self) -> None:
        """Start full."""
        self.charge_seconds = FULL_SECONDS
        self.is_dead = False

    @property
    def fraction(self) -> float:
        """How full the battery is, 0 to 1 (for the heads-up display)."""
        return self.charge_seconds / FULL_SECONDS

    def tick(self, *, dt: float, wants_light: bool) -> bool:
        """Draw power (draining) or rest (refilling) for a frame.

        Args:
            dt: The frame's time, in seconds.
            wants_light: Whether the kid holds fire with the laser pointer.

        Returns:
            True when the battery draws power this frame (the laser warming up or shining).

        """
        if wants_light and not self.is_dead and self.charge_seconds > TIME_TOLERANCE:
            self.charge_seconds -= dt
            if self.charge_seconds <= TIME_TOLERANCE:
                self.charge_seconds = 0.0
                self.is_dead = True
            return True
        self.charge_seconds = min(FULL_SECONDS, self.charge_seconds + RECHARGE_PER_SECOND * dt)
        if self.is_dead and self.charge_seconds >= REVIVE_SECONDS - TIME_TOLERANCE:
            self.is_dead = False
        return False


class LaserDot(AnimatedSprite):
    """The red dot a shining laser pointer makes on the lawn: hidden until it shines."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(self, *, groups: pygame.sprite.LayeredDirty[Any] | None) -> None:
        """Load the dot, hidden.

        Args:
            groups: The sprite group to join (a group of its own when None).

        """
        super().__init__(filename=str(DOT_FILE), groups=groups)
        self.world_x = 0.0
        self.world_y = 0.0
        self.hidden = True
        self.play('glow')

    def centre(self) -> tuple[float, float]:
        """Return the dot's centre in the world.

        Returns:
            The point.

        """
        return (self.world_x + DOT_SIZE / 2, self.world_y + DOT_SIZE / 2)

    def show_at(self, *, centre: tuple[float, float]) -> None:
        """Shine the dot with its centre on a point."""
        self.world_x = centre[0] - DOT_SIZE / 2
        self.world_y = centre[1] - DOT_SIZE / 2
        self.hidden = False

    def go_out(self) -> None:
        """Hide the dot (the laser isn't shining)."""
        self.hidden = True

    def dt_tick(self, dt: float) -> None:
        """Flicker the glow (the pose rule)."""
        AnimatedSprite.update(self, dt)

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: it flickers in ``dt_tick`` only."""
