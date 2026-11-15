"""The run's state: the stage, the neighbors left, each player's lives (feature plan 7, Task 4).

One frozen model passed between scenes in its JSON form, as the roster is, so a replay rebuilds
any scene. The next stage keeps only the neighbors saved; a player out of lives comes back with
one; a stage that ends with nobody saved ends the run.
"""

from __future__ import annotations

import pydantic
import pytest

from zombies_aint_my_neighbors.roster import MAXIMUM_PLAYERS
from zombies_aint_my_neighbors.run_state import (
    FIRST_STAGE_NEIGHBORS,
    LIVES_AFTER_BEING_OUT,
    LIVES_PER_PLAYER,
    NeighborKind,
    RunState,
)


def test_a_new_run_starts_on_stage_1_with_8_neighbors_alternating_and_full_lives():
    """The plan's numbers: 8 neighbors, the two kinds by turns; 3 lives for every slot."""
    run = RunState.new_run()

    assert (FIRST_STAGE_NEIGHBORS, LIVES_PER_PLAYER, LIVES_AFTER_BEING_OUT) == (8, 3, 1)
    assert run.stage == 1
    assert run.neighbors == (NeighborKind.PIZZA_TEEN, NeighborKind.LAWN_CHAIR_READER) * 4
    assert run.lives == (3,) * MAXIMUM_PLAYERS


def test_losing_a_life_takes_one_from_that_slot_only_and_never_below_none():
    """A knockout costs one life; a slot already out stays at none."""
    run = RunState.new_run().lose_life(slot_index=1)

    assert run.lives == (3, 2, 3, 3)
    out = run.lose_life(slot_index=1).lose_life(slot_index=1).lose_life(slot_index=1)
    assert out.lives[1] == 0
    assert out.is_out(slot_index=1)
    assert not out.is_out(slot_index=0)


def test_the_next_stage_keeps_only_the_neighbors_rescued_and_brings_players_back():
    """Stage 2 has the rescued neighbors, in the order rescued; a player out returns with 1 life."""
    run = RunState.new_run().lose_life(slot_index=2).lose_life(slot_index=2).lose_life(slot_index=2)
    run = run.lose_life(slot_index=0)
    rescued = (NeighborKind.LAWN_CHAIR_READER, NeighborKind.PIZZA_TEEN)

    following = run.next_stage(rescued=rescued)

    assert following.stage == 2
    assert following.neighbors == rescued
    assert following.lives == (2, 3, 1, 3)


def test_a_stage_with_nobody_rescued_has_no_next_stage():
    """At least one neighbor must be saved to go on (the genre's rule)."""
    with pytest.raises(ValueError, match='nobody was rescued'):
        RunState.new_run().next_stage(rescued=())


def test_the_run_survives_its_json_form():
    """A replay passes scenes their arguments as JSON: the run comes back equal."""
    run = RunState.new_run().lose_life(slot_index=3).next_stage(rescued=(NeighborKind.PIZZA_TEEN,))

    assert RunState.model_validate(run.model_dump(mode='json')) == run


def test_the_run_is_frozen_and_takes_no_unknown_fields():
    """It is changed only by returning a new run."""
    run = RunState.new_run()

    with pytest.raises(pydantic.ValidationError):
        run.stage = 5  # type: ignore[misc]
    with pytest.raises(pydantic.ValidationError):
        RunState.model_validate({**run.model_dump(mode='json'), 'score': 10})


@pytest.mark.parametrize('lives', [(4, 3, 3, 3), (3, 3, 3), (-1, 3, 3, 3)])
def test_lives_must_be_one_per_slot_within_the_limit(lives):
    """Four slots, each 0 to 3."""
    with pytest.raises(pydantic.ValidationError):
        RunState(stage=1, neighbors=(), lives=lives)
