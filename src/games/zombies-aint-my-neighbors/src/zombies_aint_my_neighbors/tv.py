"""A TV in the yard: a world sprite showing static that a Lawn Zombie pops out of.

Feature plan 5 (plans/2026-11-14-zombies-aint-my-neighbors-5-zombies.md), Task 5; the props
BOM's TV (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md). Each TV waits 6 to 9 s, drawn
from the random stream it is given (the scene's named ``zombies_aint_my_neighbors.tv-spawns``,
so a replay repeats the waits), then plays ``spawn``; the zombie is due when the pop ends.

The caps (3 zombies per TV, 10 in all) are the scene's to check, since only it sees every TV; it
passes the answer to ``tick_spawning``. A TV counts a zombie when its spawn starts, so two TVs
starting together can't pass the cap. A TV whose wait runs out while it may not spawn skips that
spawn and waits again. TVs are not solid (feature plan 5, Collisions).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Self, override

from glitchygames.sprites import AnimatedSprite
from glitchygames.world import CoordinateSpace
from zombies_aint_my_neighbors.kid import SPRITES_DIRECTORY, TIME_TOLERANCE

if TYPE_CHECKING:
    import random

    import pygame

# Feature plan 5: each TV waits this long between spawns
SPAWN_MINIMUM_SECONDS: Final = 6.0
SPAWN_MAXIMUM_SECONDS: Final = 9.0
# Feature plan 5: zombies alive per TV, and in all
ZOMBIES_PER_TV: Final = 3
ZOMBIES_IN_ALL: Final = 10
# The props BOM: spawn is 4 frames of 0.08 s; the pop is frame 2, so it ends after 3
SPAWN_FRAME_SECONDS: Final = 0.08
POP_SECONDS: Final = 3 * SPAWN_FRAME_SECONDS
SPAWN_SECONDS: Final = 4 * SPAWN_FRAME_SECONDS
# The TV's frame and the zombie's, in native pixels
TV_SIZE: Final = 48
ZOMBIE_WIDTH: Final = 32
ZOMBIE_HEIGHT: Final = 48
# How far below the TV's feet the zombie's stand, so it is drawn in front (depth by feet)
SPAWN_STEP_FORWARD: Final = 6
# The sprite file's name
SPRITE_NAME: Final = 'tv'


def may_spawn(*, zombies_from_this_tv: int, zombies_in_all: int) -> bool:
    """Return whether a TV may start a spawn under the caps.

    Args:
        zombies_from_this_tv: Zombies alive (or popping out) from this TV.
        zombies_in_all: Zombies alive (or popping out) from every TV.

    Returns:
        True when both are below their caps.

    """
    return zombies_from_this_tv < ZOMBIES_PER_TV and zombies_in_all < ZOMBIES_IN_ALL


class Tv(AnimatedSprite):
    """A TV showing static; every 6 to 9 s, a zombie pops out of it."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self,
        *,
        world_x: float,
        world_y: float,
        stream: random.Random,
        groups: pygame.sprite.LayeredDirty[Any] | None,
    ) -> None:
        """Load the TV's sprite, place it, and draw its first wait.

        Args:
            world_x: The frame's left edge in the world.
            world_y: The frame's top edge in the world.
            stream: The random stream its waits are drawn from.
            groups: The sprite group to join (a group of its own when None).

        """
        super().__init__(filename=str(SPRITES_DIRECTORY / f'{SPRITE_NAME}.toml'), groups=groups)
        self.world_x = world_x
        self.world_y = world_y
        self.stream = stream
        self.seconds_until_spawn = self._draw_wait()
        # Seconds into the current spawn (None: not spawning), and whether its zombie came out
        self.spawning_seconds: float | None = None
        self.zombie_out = False
        # Zombies from this TV alive or popping out (zombies never die until Feature 6)
        self.zombies = 0
        self._started_animation: str | None = None

    def _draw_wait(self) -> float:
        """Return a wait before the next spawn, drawn from the stream.

        Returns:
            Seconds, from 6 to 9.

        """
        return self.stream.uniform(SPAWN_MINIMUM_SECONDS, SPAWN_MAXIMUM_SECONDS)

    @property
    def is_spawning(self) -> bool:
        """Whether the spawn is playing."""
        return self.spawning_seconds is not None

    def tick_spawning(self, *, dt: float, allowed: bool) -> bool:
        """Count down to the next spawn, start it, and say when its zombie is due.

        Args:
            dt: The frame's time, in seconds.
            allowed: Whether the caps allow this TV to start a spawn now.

        Returns:
            True on the one frame the pop ends: the scene puts a zombie at ``spawn_point``.

        """
        if self.spawning_seconds is not None:
            self.spawning_seconds += dt
            if not self.zombie_out and self.spawning_seconds >= POP_SECONDS - TIME_TOLERANCE:
                self.zombie_out = True
                return True
            if self.spawning_seconds >= SPAWN_SECONDS - TIME_TOLERANCE:
                self.spawning_seconds = None
            return False
        self.seconds_until_spawn -= dt
        if self.seconds_until_spawn > TIME_TOLERANCE:
            return False
        self.seconds_until_spawn = self._draw_wait()
        if allowed:
            self.spawning_seconds = 0.0
            self.zombie_out = False
            self.zombies += 1
        return False

    def spawn_point(self) -> tuple[float, float]:
        """Return where a zombie from this TV stands: centred on it, just in front.

        Returns:
            The zombie frame's top-left corner in the world.

        """
        return (
            self.world_x + (TV_SIZE - ZOMBIE_WIDTH) / 2,
            self.world_y + TV_SIZE - ZOMBIE_HEIGHT + SPAWN_STEP_FORWARD,
        )

    def dt_tick(self, dt: float) -> None:
        """Pose the TV for this frame: static, or the spawn.

        Args:
            dt: The frame's time, in seconds.

        """
        name = 'spawn' if self.is_spawning else 'static'
        if name != self._started_animation:
            self.play(name)
            self._started_animation = name
        AnimatedSprite.update(self, dt)
        image = self.drawn_frame_surface()
        if self.image is not image:
            self.image = image
            self.dirty = 1

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: the animation advances in ``dt_tick`` only."""
