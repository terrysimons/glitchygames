"""The run's state: the stage, the neighbors left to save, and each player's lives.

Feature plan 7 (plans/2026-11-15-zombies-aint-my-neighbors-7-neighbors-and-lives.md). One frozen
model, passed from scene to scene in its JSON form (``model_dump(mode='json')``), as the roster
is, so a replay rebuilds any scene from its arguments. It changes only by returning a new run:
``lose_life`` for a knockout, ``next_stage`` when a stage is cleared. The next stage brings back
only the neighbors saved (the genre's shrinking pool), and a player out of lives returns with
one; a stage that ends with nobody saved has no next stage.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Self

from pydantic import BaseModel, ConfigDict, Field

from zombies_aint_my_neighbors.roster import MAXIMUM_PLAYERS

# Feature plan 7
FIRST_STAGE_NEIGHBORS: Final = 8
LIVES_PER_PLAYER: Final = 3
LIVES_AFTER_BEING_OUT: Final = 1


class NeighborKind(StrEnum):
    """A neighbor to save (character BOM section 6): its sprite file's name."""

    PIZZA_TEEN = 'pizza_teen'
    LAWN_CHAIR_READER = 'lawn_chair_reader'


type Lives = Annotated[int, Field(ge=0, le=LIVES_PER_PLAYER)]


class RunState(BaseModel):
    """Where a run is: its stage, the neighbors this stage has, each slot's lives."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    stage: Annotated[int, Field(ge=1)]
    # This stage's neighbors, in the order they are placed
    neighbors: tuple[NeighborKind, ...]
    # Lives left, one per player slot (a slot nobody holds keeps its full count)
    lives: Annotated[
        tuple[Lives, ...], Field(min_length=MAXIMUM_PLAYERS, max_length=MAXIMUM_PLAYERS)
    ]

    @classmethod
    def new_run(cls) -> Self:
        """Return a run's start: stage 1, its 8 neighbors by turns, every slot's lives full.

        Returns:
            The run.

        """
        kinds = tuple(NeighborKind)
        return cls(
            stage=1,
            neighbors=tuple(kinds[index % len(kinds)] for index in range(FIRST_STAGE_NEIGHBORS)),
            lives=(LIVES_PER_PLAYER,) * MAXIMUM_PLAYERS,
        )

    def is_out(self, *, slot_index: int) -> bool:
        """Return whether a slot's player has no lives left.

        Returns:
            True when out.

        """
        return self.lives[slot_index] == 0

    def lose_life(self, *, slot_index: int) -> Self:
        """Return the run with one life fewer for a slot (never below none).

        Returns:
            The new run.

        """
        lives = list(self.lives)
        lives[slot_index] = max(0, lives[slot_index] - 1)
        return self.model_copy(update={'lives': tuple(lives)})

    def next_stage(self, *, rescued: tuple[NeighborKind, ...]) -> Self:
        """Return the next stage's run: only the neighbors saved, players out back with one life.

        Args:
            rescued: The neighbors rescued this stage, in the order rescued.

        Returns:
            The next stage's run.

        Raises:
            ValueError: When nobody was rescued: the run is over.

        """
        if not rescued:
            message = 'nobody was rescued: the run has no next stage'
            raise ValueError(message)
        return type(self)(
            stage=self.stage + 1,
            neighbors=rescued,
            lives=tuple(lives or LIVES_AFTER_BEING_OUT for lives in self.lives),
        )


def as_run(run: RunState | dict[str, object] | None) -> RunState:
    """Return a run from a run, its JSON form (as a replay passes it back) or None.

    Returns:
        The run (a new run for None).

    """
    if run is None:
        return RunState.new_run()
    if isinstance(run, RunState):
        return run
    return RunState.model_validate(run)
