"""The laser pointer: its battery, and the dot its light makes on the lawn.

Feature plan 8 (plans/2026-11-15-zombies-aint-my-neighbors-8-laser-pointer.md). The battery
gives 3 s of shine when full: shining drains it 1 s a second, and not shining (whichever weapon
the kid holds) refills it at 0.3 s a second, 10 s from empty. Run flat, it is dead until it has
refilled to 1.0 s, so it can't flicker on and off at empty. The order within a frame: a battery
in use drains (and dies on reaching empty); a resting one refills (and wakes on reaching 1.0 s).
The light itself waits ``WARM_UP_SECONDS`` of drawing before it shows (the kid counts it), so a
tapped trigger spends charge and never lights (the owner, 2026-11-15).

While the dot shines, a beam runs from the laser pointer's tip to it, fading in and out (the
owner, 2026-11-15: "a beam shining to the laser point but the beam is fading in and out with
alpha"). It is drawn in code each frame it shines, as the yard and the heads-up display are, its
opacity a smooth pulse on the frames it has shone, so a replay repeats it.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Final, Self, override

import pygame

from glitchygames.sprites import AnimatedSprite, Sprite
from glitchygames.world import CoordinateSpace
from zombies_aint_my_neighbors.tolerances import TIME_TOLERANCE

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
# The beam: its red, its width, and its opacity's pulse (low to high and back, twice a second)
BEAM_COLOUR: Final = (255, 56, 56)
BEAM_WIDTH: Final = 2
BEAM_ALPHA_LOW: Final = 64
BEAM_ALPHA_HIGH: Final = 192
BEAM_PULSES_PER_SECOND: Final = 2.0


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


def beam_alpha(*, seconds: float) -> int:
    """Return the beam's opacity after shining some seconds: a smooth pulse, low to high and back.

    Returns:
        0 to 255.

    """
    phase = 0.5 - 0.5 * math.cos(2 * math.pi * BEAM_PULSES_PER_SECOND * seconds)
    return round(BEAM_ALPHA_LOW + (BEAM_ALPHA_HIGH - BEAM_ALPHA_LOW) * phase)


class LaserBeam(Sprite):
    """The beam from a laser pointer's tip to its dot, fading in and out; hidden when out."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(self, *, groups: pygame.sprite.LayeredDirty[Any] | None) -> None:
        """Make the beam, hidden.

        Args:
            groups: The sprite group to join (a group of its own when None).

        """
        super().__init__(x=0, y=0, width=1, height=1, name='Laser beam', groups=groups)
        self.world_x = 0.0
        self.world_y = 0.0
        self.hidden = True
        self.alpha = BEAM_ALPHA_LOW
        # Seconds it has shone without a break (its pulse's clock)
        self._seconds = 0.0

    def shine(self, *, start: tuple[float, float], end: tuple[float, float], dt: float) -> None:
        """Draw the beam from one point to another, at this frame's opacity.

        Args:
            start: The laser pointer's tip, in the world.
            end: The dot's centre, in the world.
            dt: The frame's time, in seconds.

        """
        self._seconds += dt
        self.alpha = beam_alpha(seconds=self._seconds)
        margin = BEAM_WIDTH
        left = math.floor(min(start[0], end[0])) - margin
        top = math.floor(min(start[1], end[1])) - margin
        right = math.ceil(max(start[0], end[0])) + margin
        bottom = math.ceil(max(start[1], end[1])) + margin
        image = pygame.Surface((right - left, bottom - top), pygame.SRCALPHA)
        pygame.draw.line(
            image,
            (*BEAM_COLOUR, self.alpha),
            (start[0] - left, start[1] - top),
            (end[0] - left, end[1] - top),
            BEAM_WIDTH,
        )
        self.image = image
        self.world_x = float(left)
        self.world_y = float(top)
        self.hidden = False
        self.dirty = 1

    def go_out(self) -> None:
        """Hide the beam; its pulse starts again next time."""
        self.hidden = True
        self._seconds = 0.0

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: its kid draws it in ``dt_tick`` (the pose rule)."""
