"""The attract demo's plan: four kids clear stage 1 together (feature plan 13).

The demo (``demos/neighborhood_four_kids.jsonl.gz``) is recorded steered live by the planner's
steering (``scripts.demo_inputs.ZombiesDemoSteering``, ``plan_neighborhood_route.demo_steering``);
``plan_demo`` plays the stage the same way under the goldens' seed and sets the demo's length.
These tests hold the plan, and the shipped demo replayed as the attract scene replays it, to what
the owner asked a passer-by to see: four kids running round zapping zombies, destroying TVs and
saving neighbors, until one reaches the open gate and all four cheer. A gameplay change that
breaks that fails here before a stale demo ships. The plan's routes are what its run held, a
by-product the recording does not use.
"""

from __future__ import annotations

import itertools
from importlib import resources

import pytest
from scripts.demo_inputs import (
    ZOMBIES_DEMO_FRAME_COUNT,
    ZOMBIES_DEMO_PAD_INSTANCE_IDS,
    ZOMBIES_DEMO_PADS,
)
from scripts.plan_neighborhood_route import DemoPlan, plan_demo

import zombies_aint_my_neighbors
from glitchygames.audio import reserve_inner_game_channels
from glitchygames.audio.engine import DEFAULT_LIBRARY_CHANNELS, DEFAULT_LIVE_POOL, LEGACY_CHANNELS
from glitchygames.audio.voices import reserve_channels
from glitchygames.engine.game_engine import CURRENT_ENGINE_SLOT
from glitchygames.inner_game import InnerGame, InnerGameState
from zombies_aint_my_neighbors.demo_neighborhood import (
    DEMO_PAD_INSTANCE_IDS,
    DemoNeighborhoodScene,
)
from zombies_aint_my_neighbors.kid import KidState

# The demo's length, in 1/60 s frames: 20 to 45 seconds (the design's target is 20 to 30;
# past 45 goes to the owner, not into the demo)
SHORTEST_DEMO_FRAMES = 20 * 60
LONGEST_DEMO_FRAMES = 45 * 60
# The shipped demo, and the size it was recorded at
SHIPPED_DEMO = (
    resources.files(zombies_aint_my_neighbors) / 'demos' / 'neighborhood_four_kids.jsonl.gz'
)
DEMO_SIZE = (800, 480)


@pytest.fixture(scope='module')
def demo_plan() -> DemoPlan:
    """Plan the demo once for the module (it plays the whole stage).

    Returns:
        The plan.

    """
    return plan_demo()


def test_the_demo_plan_clears_the_stage_at_the_gate_before_the_card(demo_plan):
    """The stage clears (a kid at the open gate), the kids cheer, and it ends before the card."""
    assert 0 < demo_plan.cleared_at < demo_plan.recording_frames < demo_plan.card_at
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


def test_the_demo_plan_holds_nothing_on_frame_0(demo_plan):
    """A scripted session can't post input before frame 0, so the plan starts on frame 1."""
    assert all(stretch.first_frame >= 1 for route in demo_plan.routes for stretch in route)


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


def test_the_recipes_frame_count_is_still_the_plans(demo_plan):
    """The demo records the plan's length: a gameplay change fails here until re-planned."""
    assert demo_plan.recording_frames == ZOMBIES_DEMO_FRAME_COUNT


def test_the_demo_pads_are_the_demo_neighborhoods():
    """The recipe's stand-in pads are the pads the demo neighborhood's roster joins."""
    assert ZOMBIES_DEMO_PAD_INSTANCE_IDS == DEMO_PAD_INSTANCE_IDS
    assert tuple(pad.instance_id for pad in ZOMBIES_DEMO_PADS) == DEMO_PAD_INSTANCE_IDS


@pytest.fixture
def one_inner_game_declared() -> None:
    """Partition the mixer and declare one inner game, as the game's title does at startup."""
    reserve_channels(
        live_pool=DEFAULT_LIVE_POOL,
        library_channels=DEFAULT_LIBRARY_CHANNELS,
        legacy_channels=LEGACY_CHANNELS,
    )
    reserve_inner_game_channels(games=1)


@pytest.mark.usefixtures('one_inner_game_declared')
def test_the_shipped_demo_shows_what_was_promised():
    """Replayed as the attract scene replays it, the demo shows four kids clearing stage 1.

    Each frame the replayed stage is read: every kid walks and zaps, a TV is destroyed, a zombie
    zapped, neighbors rescued, the stage cleared at the gate with all four cheering, the card
    never shown, and the replay matches its recording to the end.
    """
    game = InnerGame.replay(
        command='zombies-aint-my-neighbors',
        path=SHIPPED_DEMO,
        name='attract demo',
        size=DEMO_SIZE,
    )
    starts: dict[int, tuple[float, float]] = {}
    moved: set[int] = set()
    fired: set[int] = set()
    zapped = 0
    dying_before: set[int] = set()
    scenes: set[type] = set()
    scene = None
    running = game.outcome.state is InnerGameState.RUNNING
    while running:
        scene = game.context.value(slot=CURRENT_ENGINE_SLOT).engine.scene_manager.active_scene
        scenes.add(type(scene))
        if isinstance(scene, DemoNeighborhoodScene):
            positions = {slot: (kid.world_x, kid.world_y) for slot, kid in scene.kids.items()}
            starts = starts or positions
            moved.update(slot for slot, place in positions.items() if place != starts[slot])
            fired.update(scene.zap_owners.values())
            dying_now = {id(zombie) for zombie in scene.zombies if zombie.is_dying}
            zapped += len(dying_now - dying_before)
            dying_before = dying_now
        running = game.step()

    assert game.outcome.state is InnerGameState.ENDED, game.outcome
    assert game.outcome.diverged is False, game.outcome.report
    assert scenes == {DemoNeighborhoodScene}
    assert isinstance(scene, DemoNeighborhoodScene)
    assert moved == {0, 1, 2, 3}
    assert fired == {0, 1, 2, 3}
    assert zapped >= 1
    assert sum(tv.is_destroyed for tv in scene.tvs) >= 1
    assert scene.rescued
    assert scene.stage_cleared
    assert all(kid.state is KidState.CHEERING for kid in scene.kids.values())
