"""Tests for the headless Drawing Fire simulation (scripts/simulate_drawing_fire.py)."""

from __future__ import annotations

from scripts import simulate_drawing_fire
from scripts.simulate_drawing_fire import MAX_BATTLE_SECONDS, simulate

from glitchygames.examples.drawing_fire.battle import Side

# Small armies keep the battles in these tests quick
TEST_SOLDIERS_PER_SIDE = 3
# A step this long keeps them quicker still
TEST_FRAME_SECONDS = 1 / 30


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
