"""When a zombie groans: sometimes, when it sees something new to chase (feature plan 10).

The owner, 2026-11-15: "Zombies should make a zombie sound sometimes when they see something new
to chase." A zombie with a new target (``Zombie.new_target``: a kid, a neighbor or a laser dot it
was not chasing; its first counts) groans one time in three; never within 3 s of its own last
groan, and never within half a second of any groan starting, so a crowd never moans in chorus.
The rests are checked before the roll, so a zombie that may not groan draws nothing from the
stream. The scene rolls from a named stream (``GROAN_STREAM``), so a replay repeats every groan.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from zombies_aint_my_neighbors.tolerances import TIME_TOLERANCE

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable

GROAN_CHANCE: Final = 1 / 3
GROAN_REST_SECONDS: Final = 3.0
GROAN_SPACING_SECONDS: Final = 0.5
GROAN_STREAM: Final = 'zombies_aint_my_neighbors.zombie-groans'


class GroanTimer:
    """Says whether a zombie with a new target groans now, and remembers when groans began."""

    def __init__(self) -> None:
        """Start with no groan heard."""
        self._last_groan = -math.inf
        self._last_groan_by_zombie: dict[Hashable, float] = {}

    def should_groan(self, *, zombie: Hashable, now: float, roll: Callable[[], float]) -> bool:
        """Return whether a zombie that just found a new target groans, remembering it if so.

        Args:
            zombie: The zombie (anything that tells zombies apart).
            now: The scene's game time, in seconds.
            roll: Draws a number in [0, 1); called only when the rests allow a groan.

        Returns:
            True when it groans.

        """
        if now - self._last_groan < GROAN_SPACING_SECONDS - TIME_TOLERANCE:
            return False
        last_own = self._last_groan_by_zombie.get(zombie, -math.inf)
        if now - last_own < GROAN_REST_SECONDS - TIME_TOLERANCE:
            return False
        if roll() >= GROAN_CHANCE:
            return False
        self._last_groan = now
        self._last_groan_by_zombie[zombie] = now
        return True
