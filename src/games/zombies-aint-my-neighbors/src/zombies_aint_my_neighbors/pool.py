"""A pool of sprites built before play and reused: nothing loads a sprite file mid-game.

Master plan decision 11: heavy work happens before play. The engine keeps no cache of loaded
sprite files, so each new sprite reads and parses its TOML: a Lawn Zombie took 27 to 41 ms (two
or three dropped frames at 60 fps) and a zap about 2 ms (measured 2026-11-15). The neighborhood
builds its zombies and zaps in a pool each, takes one when it spawns or fires, and gives it back
when it has gone. A pool that runs dry makes one more (a load) and logs a warning, since its size
was meant to cover every case. Sprites are taken from the end, so a replay takes the same ones.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

LOG = logging.getLogger('game.zombies_aint_my_neighbors.pool')


class SpritePool[Pooled]:
    """Sprites made up front, taken and given back."""

    def __init__(self, *, make: Callable[[], Pooled], size: int) -> None:
        """Make the pool's sprites now.

        Args:
            make: Makes one sprite, out of every group.
            size: How many to make.

        """
        self._make = make
        self.size = size
        self._free = [make() for _ in range(size)]
        # Sprites given back in all (to check reuse)
        self.given_back = 0

    @property
    def free(self) -> int:
        """How many sprites are ready to take."""
        return len(self._free)

    def take(self) -> Pooled:
        """Return a free sprite (one more made, with a warning, when none is free).

        Returns:
            The sprite.

        """
        if self._free:
            return self._free.pop()
        LOG.warning('sprite pool ran dry (size %d): making one more mid-game', self.size)
        return self._make()

    def give_back(self, sprite: Pooled) -> None:
        """Return a sprite that has gone, to be taken again."""
        self._free.append(sprite)
        self.given_back += 1
