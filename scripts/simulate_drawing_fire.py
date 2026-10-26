"""Play Drawing Fire battles headless (computer against computer) and report how they go.

It seeds the engine, builds each battle the way the game does and steps it with the computer
driver, with no window. One line is printed per seed, then a summary: wins per army, draws
(both armies fell in the same step), battles given up at the time limit, and the mean and
longest battle. Use it to tune the battle's numbers.

Usage:
    uv run python -m scripts.simulate_drawing_fire [--seeds N] [--soldiers-per-side N]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from drawing_fire.battle import ARMY_NAMES, SOLDIERS_PER_SIDE, Side
from drawing_fire.drivers import computer_intents, muster_battle
from glitchygames.randomness import seed_engine_random

if TYPE_CHECKING:
    from collections.abc import Sequence

# The screen the game plays on
FIELD_WIDTH = 800
FIELD_HEIGHT = 480
# A battle that runs this long (game seconds) is given up as a stalemate
MAX_BATTLE_SECONDS = 600.0
DEFAULT_SEED_COUNT = 20


@dataclass(frozen=True)
class SimulationResult:
    """How one simulated battle ended."""

    seed: int
    winner: Side | None
    seconds: float
    survivors: int

    @property
    def drawn(self) -> bool:
        """Whether both armies fell (in the same step): no winner, and nobody left."""
        return self.winner is None and self.survivors == 0

    @property
    def outcome(self) -> str:
        """The result in words: the winning army, a draw, or no winner (the time limit)."""
        if self.winner is not None:
            return ARMY_NAMES[self.winner]
        return 'draw' if self.drawn else 'no winner'


def simulate(
    *,
    seed: int,
    soldiers_per_side: int = SOLDIERS_PER_SIDE,
    frame_seconds: float = 1 / 60,
    max_seconds: float = MAX_BATTLE_SECONDS,
) -> SimulationResult:
    """Play one battle, computer against computer, until it is over or the time limit.

    Args:
        seed: The engine's master seed.
        soldiers_per_side: How many soldiers each army has.
        frame_seconds: The seconds each step advances.
        max_seconds: The game seconds after which the battle is given up.

    Returns:
        How the battle ended (no winner in a draw, or when it hit the limit).

    """
    seed_engine_random(seed=seed)
    battle, minds, streams = muster_battle(
        battle_number=1,
        width=FIELD_WIDTH,
        height=FIELD_HEIGHT,
        soldiers_per_side=soldiers_per_side,
    )
    while not battle.over and battle.seconds < max_seconds:
        battle.step(
            dt=frame_seconds, intents=computer_intents(battle=battle, minds=minds, streams=streams)
        )
    return SimulationResult(
        seed=seed,
        winner=battle.winner,
        seconds=battle.seconds,
        survivors=len(battle.living(Side.PLATOON)) + len(battle.living(Side.BRIGADE)),
    )


def main(arguments: Sequence[str] | None = None) -> int:
    """Simulate battles for seeds 0..N-1 and print a line for each and a summary.

    Args:
        arguments: The command line (None: ``sys.argv[1:]``).

    Returns:
        The exit status (0).

    """
    parser = argparse.ArgumentParser(description='Simulate Drawing Fire battles headless.')
    parser.add_argument('--seeds', type=int, default=DEFAULT_SEED_COUNT, help='how many seeds')
    parser.add_argument(
        '--soldiers-per-side', type=int, default=SOLDIERS_PER_SIDE, help='soldiers per army'
    )
    options = parser.parse_args(arguments)

    results = [
        simulate(seed=seed, soldiers_per_side=options.soldiers_per_side)
        for seed in range(options.seeds)
    ]
    for result in results:
        sys.stdout.write(
            f'seed {result.seed}: {result.outcome}, {result.seconds:.1f}s, '
            f'{result.survivors} left\n'
        )
    wins = {side: sum(1 for result in results if result.winner is side) for side in Side}
    draws = sum(1 for result in results if result.drawn)
    unfinished = sum(1 for result in results if result.winner is None and not result.drawn)
    durations = [result.seconds for result in results]
    mean_seconds = sum(durations) / len(durations) if durations else 0.0
    longest_seconds = max(durations, default=0.0)
    sys.stdout.write(
        f'wins: {ARMY_NAMES[Side.PLATOON]} ({Side.PLATOON.value}) {wins[Side.PLATOON]}, '
        f'{ARMY_NAMES[Side.BRIGADE]} ({Side.BRIGADE.value}) {wins[Side.BRIGADE]}; '
        f'draws {draws}; no winner {unfinished}; '
        f'mean {mean_seconds:.1f}s, longest {longest_seconds:.1f}s\n'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
