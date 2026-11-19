"""A neighbor in the yard: idle, panicking when a zombie comes near, then saved or lost.

Feature plan 7 (plans/2026-11-15-zombies-aint-my-neighbors-7-neighbors-and-lives.md), Task 5;
character BOM section 6. A neighbor never moves. It plays ``idle``, or ``panic`` while a living
zombie stands within 96 px. A kid's touch saves it (``rescue``: ``save`` is the engine's, which
writes a sprite to a file) and a zombie's loses it
(``lose``): the neighbor hides and its effect (``saved``: 5 frames of 0.06 s; ``lost``: 5 of
0.08 s) plays where it stood, then both leave their groups (``is_gone``). The effects are built
with the neighbor, before play, so nothing loads mid-game (feature plan 6's rule).

Its places are 12 fixed spots round the yard, clear of the TVs, the starting huddle and the exit;
each stage draws its neighbors' places from a named random stream (``neighbor_places``), so a
replay repeats them. Like the kids, it poses in ``dt_tick`` and ``update`` does nothing.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Self, override

from glitchygames.collision.detection import get_collision_rect_with_margin
from glitchygames.sprites import AnimatedSprite
from glitchygames.world import CoordinateSpace
from zombies_aint_my_neighbors.kid import SPRITES_DIRECTORY, TIME_TOLERANCE
from zombies_aint_my_neighbors.zombie import TOUCH_MARGIN

if TYPE_CHECKING:
    import random
    from collections.abc import Sequence

    import pygame

    from zombies_aint_my_neighbors.exit_door import ExitDoor
    from zombies_aint_my_neighbors.kid import Kid
    from zombies_aint_my_neighbors.run_state import NeighborKind
    from zombies_aint_my_neighbors.zombie import Zombie

# Feature plan 7: a zombie this close (frame to frame) makes a neighbor panic
PANIC_DISTANCE: Final = 96
# Character BOM section 6: saved is 5 frames of 0.06 s, lost 5 of 0.08 s
SAVED_SECONDS: Final = 5 * 0.06
LOST_SECONDS: Final = 5 * 0.08
# The 12 places (a neighbor frame's top-left corner, 32x48), round the yard, clear of the TVs,
# the starting huddle and the exit door in the top hedge's middle
NEIGHBOR_PLACES: Final[tuple[tuple[int, int], ...]] = (
    (150, 120),
    (560, 110),
    (1010, 110),
    (1420, 120),
    (150, 470),
    (560, 340),
    (1010, 340),
    (1420, 470),
    (150, 800),
    (600, 820),
    (1000, 820),
    (1420, 800),
)


class NeighborState(StrEnum):
    """Where a neighbor is: standing, or being saved or lost (then gone)."""

    STANDING = 'standing'
    SAVED = 'saved'
    LOST = 'lost'


def neighbor_places(*, stream: random.Random, count: int) -> list[tuple[int, int]]:
    """Return ``count`` distinct places for a stage's neighbors, drawn from a stream.

    Args:
        stream: The named random stream (``zombies_aint_my_neighbors.neighbor-places``).
        count: How many neighbors the stage has (at most 12).

    Returns:
        The places, in the order the neighbors are placed.

    """
    return stream.sample(NEIGHBOR_PLACES, count)


def touching(first: Kid | Zombie | Neighbor, second: Neighbor | ExitDoor) -> bool:
    """Return whether two world sprites touch: their hitboxes, each shrunk by the margin, meet.

    The same forgiveness as a zombie touching a kid (feature plan 5).

    Returns:
        True when they meet.

    """
    first_rect = get_collision_rect_with_margin(
        first, first.world_x, first.world_y, margin=TOUCH_MARGIN
    )
    second_rect = get_collision_rect_with_margin(
        second, second.world_x, second.world_y, margin=TOUCH_MARGIN
    )
    return first_rect.colliderect(second_rect)


class NeighborEffect(AnimatedSprite):
    """Being saved or lost, played once where a neighbor stood."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(self, *, name: str, groups: pygame.sprite.LayeredDirty[Any] | None) -> None:
        """Load the effect, hidden until it plays.

        Args:
            name: ``saved`` or ``lost``.
            groups: The sprite group to join (a group of its own when None).

        """
        super().__init__(filename=str(SPRITES_DIRECTORY / f'{name}.toml'), groups=groups)
        self.name = name
        self.world_x = 0.0
        self.world_y = 0.0
        self.hidden = True

    def start(self, *, world_x: float, world_y: float) -> None:
        """Show the effect from its first frame at a place."""
        self.world_x = world_x
        self.world_y = world_y
        self.hidden = False
        self.play(self.name)

    def dt_tick(self, dt: float) -> None:
        """Advance the effect (the pose rule)."""
        AnimatedSprite.update(self, dt)

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: it advances in ``dt_tick`` only."""


class Neighbor(AnimatedSprite):
    """A neighbor to save: never moves; panics near zombies; saved or lost, then gone."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self,
        *,
        kind: NeighborKind,
        world_x: float,
        world_y: float,
        groups: pygame.sprite.LayeredDirty[Any] | None,
    ) -> None:
        """Load the neighbor and its two effects, and place it.

        Args:
            kind: Which neighbor (its sprite file's name).
            world_x: Its frame's left edge in the world.
            world_y: Its frame's top edge in the world.
            groups: The sprite group to join (a group of its own when None).

        """
        super().__init__(filename=str(SPRITES_DIRECTORY / f'{kind}.toml'), groups=groups)
        self.kind = kind
        self.world_x = world_x
        self.world_y = world_y
        self.state = NeighborState.STANDING
        self.panicking = False
        self.hidden = False
        self.is_gone = False
        self._effects = {
            NeighborState.SAVED: NeighborEffect(name='saved', groups=groups),
            NeighborState.LOST: NeighborEffect(name='lost', groups=groups),
        }
        # The effect playing (None while standing), and seconds into it
        self.effect: NeighborEffect | None = None
        self._effect_seconds = 0.0
        self._started_animation: str | None = None

    @property
    def is_standing(self) -> bool:
        """Whether the neighbor is still there to save (or lose)."""
        return self.state is NeighborState.STANDING

    @property
    def playing_effect(self) -> NeighborEffect:
        """The rescue or loss playing, once ``rescue`` or ``lose`` has started it.

        Raises:
            RuntimeError: While the neighbor still stands (no effect has started).

        """
        if self.effect is None:
            message = f'{self.kind} still stands: no rescue or loss is playing'
            raise RuntimeError(message)
        return self.effect

    def notice(self, *, zombies: Sequence[Zombie]) -> None:
        """Panic when a living zombie is within the panic distance, frame to frame."""
        self.panicking = any(
            not zombie.is_dying
            and math.hypot(zombie.world_x - self.world_x, zombie.world_y - self.world_y)
            <= PANIC_DISTANCE
            for zombie in zombies
        )

    def rescue(self) -> bool:
        """Be saved by a kid: the saved effect plays where the neighbor stood.

        Returns:
            True when saved now; False when already saved or lost.

        """
        return self._end(NeighborState.SAVED)

    def lose(self) -> bool:
        """Be lost to a zombie: the lost effect plays where the neighbor stood.

        Returns:
            True when lost now; False when already saved or lost.

        """
        return self._end(NeighborState.LOST)

    def _end(self, state: NeighborState) -> bool:
        """Leave standing for an end, starting its effect.

        Returns:
            True when the neighbor was standing.

        """
        if not self.is_standing:
            return False
        self.state = state
        self.hidden = True
        self.effect = self._effects[state]
        self.effect.start(world_x=self.world_x, world_y=self.world_y)
        self._effect_seconds = 0.0
        return True

    def dt_tick(self, dt: float) -> None:
        """Pose the neighbor (idle or panic), or play its effect and leave when it ends.

        Args:
            dt: The frame's time, in seconds.

        """
        if self.effect is not None:
            # A gone neighbor's tick lands here too and ends again: the scene drops it anyway
            self._effect_seconds += dt
            seconds = SAVED_SECONDS if self.state is NeighborState.SAVED else LOST_SECONDS
            if self._effect_seconds >= seconds - TIME_TOLERANCE:
                self.is_gone = True
                self.kill()
                return
            self.effect.dt_tick(dt)
            return
        name = 'panic' if self.panicking else 'idle'
        if name != self._started_animation:
            self.play(name)
            self._started_animation = name
        AnimatedSprite.update(self, dt)

    @override
    def kill(self) -> None:
        """Leave the yard, with both effects."""
        for effect in self._effects.values():
            effect.kill()
        super().kill()

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: it poses in ``dt_tick`` only."""
