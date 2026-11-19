"""The attract demo's plan: four kids clear stage 1 together (feature plan 13).

The demo (``demos/neighborhood_four_kids.jsonl.gz``) is recorded from routes the planner makes
by playing the stage under the goldens' seed (``scripts.plan_neighborhood_route.plan_demo``).
These tests hold the plan to what the owner asked a passer-by to see: four kids running round
zapping zombies, destroying TVs and saving neighbors, until one reaches the open gate and all
four cheer. A gameplay change that breaks that fails here before a stale demo ships.
"""

from __future__ import annotations

import itertools

import pytest
from scripts.plan_neighborhood_route import DemoPlan, plan_demo

# The demo's length, in 1/60 s frames: 20 to 45 seconds (the design's target is 20 to 30;
# past 45 goes to the owner, not into the demo)
SHORTEST_DEMO_FRAMES = 20 * 60
LONGEST_DEMO_FRAMES = 45 * 60


@pytest.fixture(scope='module')
def demo_plan() -> DemoPlan:
    """Plan the demo once for the module (it plays the whole stage).

    Returns:
        The plan.

    """
    return plan_demo()


def test_the_demo_plan_clears_the_stage_at_the_gate_before_the_card(demo_plan):
    """The stage clears (a kid at the open gate), the kids cheer, and it ends before the card."""
    assert 0 < demo_plan.cleared_at < demo_plan.card_at
    assert demo_plan.recording_frames == demo_plan.card_at
    assert demo_plan.all_cheered


def test_every_kid_moves_and_fires_in_the_demo_plan(demo_plan):
    """All four kids play: each walks and each zaps."""
    assert demo_plan.moved_by_slot == (True, True, True, True)
    assert demo_plan.fired_by_slot == (True, True, True, True)


def test_the_demo_plan_destroys_a_tv_zaps_zombies_and_rescues(demo_plan):
    """A passer-by sees TVs destroyed, zombies zapped and neighbors saved."""
    assert demo_plan.televisions_destroyed >= 1
    assert demo_plan.zombies_zapped >= 1
    assert demo_plan.rescued >= 1


def test_the_demo_plan_ends_with_nothing_held(demo_plan):
    """Nothing is held after the clear, so the demo loops with no input stuck."""
    for route in demo_plan.routes:
        assert all(stretch.end_frame <= demo_plan.cleared_at + 1 for stretch in route)


def test_the_demo_plan_has_one_route_per_kid_in_frame_order(demo_plan):
    """One route a slot; each stretch steers or fires, and they never overlap."""
    assert len(demo_plan.routes) == 4
    for route in demo_plan.routes:
        assert all(stretch.direction != (0, 0) or stretch.fire for stretch in route)
        for earlier, later in itertools.pairwise(route):
            assert earlier.end_frame <= later.first_frame


def test_the_demo_plan_is_twenty_to_forty_five_seconds(demo_plan):
    """Long enough to show a stage, short enough to watch."""
    assert SHORTEST_DEMO_FRAMES <= demo_plan.recording_frames <= LONGEST_DEMO_FRAMES
