"""Tests for the headless Drawing Fire simulation (scripts/simulate_drawing_fire.py)."""

from __future__ import annotations

from scripts import simulate_drawing_fire
from scripts.simulate_drawing_fire import MAX_BATTLE_SECONDS, SimulationResult, simulate

from glitchygames.examples.drawing_fire.battle import SOLDIERS_PER_SIDE, Side
from glitchygames.examples.drawing_fire.drivers import computer_intents, muster_battle
from glitchygames.randomness import seed_engine_random

# Small armies keep the battles in these tests quick
TEST_SOLDIERS_PER_SIDE = 3
# A step this long keeps them quicker still
TEST_FRAME_SECONDS = 1 / 30
# Two living soldiers of one army closer than this (px) are standing on one another
PILE_UP_PIXELS = 6.0
# ...and that may last this long (s), as one passes another, but no longer
PILE_UP_SECONDS = 2.0
PILE_UP_SEEDS = (1, 2, 3, 4)


def test_a_computer_battle_ends_with_a_winner():
    """A battle plays itself to a winner inside the time limit."""
    result = simulate(
        seed=3, soldiers_per_side=TEST_SOLDIERS_PER_SIDE, frame_seconds=TEST_FRAME_SECONDS
    )
    assert result.winner is not None
    assert result.seconds < MAX_BATTLE_SECONDS
    assert result.survivors > 0


def test_the_same_seed_replays_the_same_battle():
    """Seeds make battles that replay exactly."""
    first = simulate(
        seed=8, soldiers_per_side=TEST_SOLDIERS_PER_SIDE, frame_seconds=TEST_FRAME_SECONDS
    )
    second = simulate(
        seed=8, soldiers_per_side=TEST_SOLDIERS_PER_SIDE, frame_seconds=TEST_FRAME_SECONDS
    )
    assert first == second


def test_a_battle_that_hits_the_time_limit_has_no_winner():
    """With only a moment allowed, nobody has won."""
    result = simulate(
        seed=3,
        soldiers_per_side=TEST_SOLDIERS_PER_SIDE,
        frame_seconds=TEST_FRAME_SECONDS,
        max_seconds=0.5,
    )
    assert result.winner is None
    assert result.survivors == 2 * TEST_SOLDIERS_PER_SIDE


def test_a_result_names_its_outcome_a_win_a_draw_or_no_winner():
    """A winner is named; nobody left is a draw; both armies still fighting is no winner."""
    won = SimulationResult(seed=0, winner=Side.PLATOON, seconds=40.0, survivors=3)
    drawn = SimulationResult(seed=1, winner=None, seconds=40.0, survivors=0)
    unfinished = SimulationResult(seed=2, winner=None, seconds=600.0, survivors=5)
    assert (won.outcome, drawn.outcome, unfinished.outcome) == (
        'Pencil Platoon',
        'draw',
        'no winner',
    )
    assert (won.drawn, drawn.drawn, unfinished.drawn) == (False, True, False)


def test_the_simulation_prints_a_summary(capsys):
    """main() prints a line per seed and the wins."""
    status = simulate_drawing_fire.main([
        '--seeds',
        '2',
        '--soldiers-per-side',
        str(TEST_SOLDIERS_PER_SIDE),
    ])
    output = capsys.readouterr().out
    assert status == 0
    assert 'seed 0' in output
    assert 'seed 1' in output
    assert 'wins' in output
    assert Side.PLATOON.value in output


def test_no_seeds_prints_an_empty_summary_without_crashing(capsys):
    """--seeds 0 simulates nothing and still reports."""
    assert simulate_drawing_fire.main(['--seeds', '0']) == 0
    assert 'wins' in capsys.readouterr().out


def overlapping_friends(battle):
    """Find the pairs of living friends standing closer than PILE_UP_PIXELS.

    Returns:
        The set of (lower id, higher id) pairs.

    """
    pairs = set()
    for side in Side:
        friends = battle.living(side)
        pairs.update(
            (first.soldier_id, second.soldier_id)
            for first_index, first in enumerate(friends)
            for second in friends[first_index + 1 :]
            if abs(first.x - second.x) < PILE_UP_PIXELS
        )
    return pairs


def test_an_army_never_stands_piled_on_one_spot():
    """Over whole default-size battles, no two living friends overlap for more than a moment.

    (Before spacing, every soldier stopped at the same crest or the same sandbag edge, and
    eight soldiers drew as one.)
    """
    for seed in PILE_UP_SEEDS:
        seed_engine_random(seed=seed)
        battle, minds, streams = muster_battle(
            battle_number=1, width=800, height=480, soldiers_per_side=SOLDIERS_PER_SIDE
        )
        overlapped_seconds: dict[tuple[int, int], float] = {}
        longest = 0.0
        while not battle.over and battle.seconds < MAX_BATTLE_SECONDS:
            battle.step(
                dt=TEST_FRAME_SECONDS,
                intents=computer_intents(battle=battle, minds=minds, streams=streams),
            )
            overlapped_seconds = {
                pair: overlapped_seconds.get(pair, 0.0) + TEST_FRAME_SECONDS
                for pair in overlapping_friends(battle)
            }
            longest = max([longest, *overlapped_seconds.values()])
        assert longest <= PILE_UP_SECONDS, f'seed {seed}: friends overlapped for {longest:.1f}s'
