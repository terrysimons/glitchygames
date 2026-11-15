"""A zap from the Channel Changer: a ring of TV static that flies, strikes or fizzles out.

Feature plan 6 (plans/2026-11-15-zombies-aint-my-neighbors-6-channel-changer.md), Task 6. A zap
leaves the remote's LED and flies its kid's aim at 320 px/s for at most 0.6 s (192 px), then
fizzles where it is (2 frames, 0.12 s) and is gone; a zap whose centre would leave the yard
fizzles at the edge. A zap that has gone is hidden and kept in its groups for the scene's pool
to reuse (``launch``): a sprite removed from every group must not be held
(tests/replay/test_removed_sprites_are_freed.py). While flying it can strike, and on the frame
its flight ends too, since its last step may be the one that meets a target: the scene asks
``first_struck`` which zombie or TV its hitbox meets (the nearest, when several) and calls
``strike``, and the zap is gone at once. Kids and other zaps are never offered to it, so it
passes through them.

The neighborhood caps a frame at 0.05 s (``MAX_FRAME_SECONDS``), so a zap moves at most 16 px
a frame (about 5 at 60 frames a second), under its own hitbox and the narrowest target's
together (28 px): testing after each move never steps over a target.

Like the kids, it moves and poses in ``dt_tick`` (the pose rule, CLAUDE.md World Space), and
``update`` does nothing.
"""

from __future__ import annotations

import math
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Self, override

from glitchygames.collision.detection import get_collision_rect
from glitchygames.sprites import AnimatedSprite
from glitchygames.world import CoordinateSpace
from zombies_aint_my_neighbors.kid import TIME_TOLERANCE

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pygame

    from zombies_aint_my_neighbors.tv import Tv
    from zombies_aint_my_neighbors.zombie import Zombie

SPRITE_FILE: Final = Path(__file__).resolve().parent / 'sprites' / 'zap.toml'
# Feature plan 6: its speed, how long it flies, its fizzle (2 frames of 0.06 s) and its size
ZAP_SPEED: Final = 320.0
ZAP_RANGE_SECONDS: Final = 0.6
FIZZLE_SECONDS: Final = 0.12
ZAP_SIZE: Final = 12


class ZapState(StrEnum):
    """Where a zap is in its short life."""

    FLYING = 'flying'
    FIZZLING = 'fizzling'
    GONE = 'gone'


class Zap(AnimatedSprite):
    """A zap of static, flying straight from a remote's LED."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self,
        *,
        centre: tuple[float, float],
        direction: tuple[float, float],
        bounds: pygame.Rect,
        groups: pygame.sprite.LayeredDirty[Any] | None,
    ) -> None:
        """Make a zap leaving a point.

        Args:
            centre: Where it leaves (its frame's centre), in the world.
            direction: Which way it flies, at unit length.
            bounds: The yard: it fizzles where its centre would leave this.
            groups: The sprite group to join (a group of its own when None).

        """
        super().__init__(filename=str(SPRITE_FILE), groups=groups)
        self.bounds = bounds
        self.launch(centre=centre, direction=direction)

    def launch(self, *, centre: tuple[float, float], direction: tuple[float, float]) -> None:
        """Start a fresh flight from a point: as new, or reused from the scene's pool.

        Args:
            centre: Where it leaves (its frame's centre), in the world.
            direction: Which way it flies, at unit length.

        """
        self.world_x = centre[0] - ZAP_SIZE / 2
        self.world_y = centre[1] - ZAP_SIZE / 2
        self.direction = direction
        self.state = ZapState.FLYING
        # Seconds in the current state, and whether its flight ended this frame (it may still
        # strike what that last step met)
        self._state_seconds = 0.0
        self._flight_ended_this_frame = False
        self.hidden = False
        self.play('fly')

    def put_away(self) -> None:
        """Be gone: hidden, kept in its groups for a pool to reuse."""
        self.state = ZapState.GONE
        self.hidden = True

    @property
    def is_live(self) -> bool:
        """Whether the zap can strike: while flying, and on the frame its flight ends."""
        return self.state is ZapState.FLYING or (
            self.state is ZapState.FIZZLING and self._flight_ended_this_frame
        )

    def centre(self) -> tuple[float, float]:
        """Return the zap's centre in the world.

        Returns:
            The point.

        """
        return (self.world_x + ZAP_SIZE / 2, self.world_y + ZAP_SIZE / 2)

    def strike(self) -> None:
        """Take the hit: the zap is gone at once."""
        self.put_away()

    def _fizzle(self) -> None:
        """Stop where it is and break up."""
        self.state = ZapState.FIZZLING
        self._state_seconds = 0.0
        self._flight_ended_this_frame = True
        self.play('fizzle')

    def _fly(self, dt: float) -> None:
        """Move along the aim, never past the range or out of the yard."""
        remaining = max(0.0, ZAP_RANGE_SECONDS - self._state_seconds)
        step = ZAP_SPEED * min(dt, remaining)
        self._state_seconds += dt
        centre_x, centre_y = self.centre()
        next_x = centre_x + self.direction[0] * step
        next_y = centre_y + self.direction[1] * step
        inside_x = min(max(next_x, self.bounds.left), self.bounds.right)
        inside_y = min(max(next_y, self.bounds.top), self.bounds.bottom)
        self.world_x = inside_x - ZAP_SIZE / 2
        self.world_y = inside_y - ZAP_SIZE / 2
        if (inside_x, inside_y) != (next_x, next_y) or (
            self._state_seconds >= ZAP_RANGE_SECONDS - TIME_TOLERANCE
        ):
            self._fizzle()

    def dt_tick(self, dt: float) -> None:
        """Fly or fizzle for this frame, and pose the zap.

        Args:
            dt: The frame's time, in seconds.

        """
        self._flight_ended_this_frame = False
        if self.state is ZapState.FLYING:
            self._fly(dt)
        elif self.state is ZapState.FIZZLING:
            self._state_seconds += dt
            if self._state_seconds >= FIZZLE_SECONDS - TIME_TOLERANCE:
                self.put_away()
                return
        AnimatedSprite.update(self, dt)

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: the zap moves and animates in ``dt_tick`` only."""


def first_struck(*, zap: Zap, targets: Sequence[Zombie | Tv]) -> Zombie | Tv | None:
    """Return the target a flying zap strikes: the nearest whose hitbox meets the zap's.

    Args:
        zap: The zap.
        targets: The zombies and TVs it may strike.

    Returns:
        The struck target, or None when it meets none (or isn't flying).

    """
    if not zap.is_live:
        return None
    zap_rect = get_collision_rect(zap, zap.world_x, zap.world_y)
    touched = [
        (get_collision_rect(target, target.world_x, target.world_y), target) for target in targets
    ]
    met = [(rect, target) for rect, target in touched if zap_rect.colliderect(rect)]
    if not met:
        return None
    _rect, nearest = min(
        met,
        key=lambda pair: math.hypot(
            pair[0].centerx - zap_rect.centerx, pair[0].centery - zap_rect.centery
        ),
    )
    return nearest
