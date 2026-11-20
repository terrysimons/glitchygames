"""Seeds that once failed a test, kept as fixtures, and run with a fresh seed every time.

The owner's rule (2026-11-15): when a test fails for operations where a seed is available (the
engine's named random streams, ``glitchygames.randomness.reset_streams``), save that seed to a
fixture for that test vector, and run every previously regressed seed. Each run runs a fresh
random seed, then the saved ones, parametrized, so a fix can't quietly regress and a new
failure is caught with its seed in hand.

A test takes ``seed`` from ``seed_cases(test=..., vector=...)``, turns it into a number with
``resolve_seed(case, node=request.node, test=..., vector=...)``, and calls
``reset_streams(seed=...)`` before building its scene. ``resolve_seed`` records the seed on the
running test, and the game's conftest adds it to every failed report (``seed_report``), so a
failure by exception keeps its seed as surely as a failed assertion. The fixtures are
``fixtures/regressed_seeds/<test>.json``: ``{"<vector>": [seed, ...]}``.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Final

FIXTURE_DIRECTORY: Final = Path(__file__).resolve().parent / 'fixtures' / 'regressed_seeds'
# The case drawn fresh at every run (a stable id, so parallel workers collect the same tests)
RANDOM_CASE: Final = 'random'
SEED_LIMIT: Final = 2**31
# Where resolve_seed keeps a running test's seed (and its fixture) on its node
SEED_ATTRIBUTE: Final = 'regressed_seed'


def saved_seeds(*, test: str, vector: str) -> list[int]:
    """Return the seeds that once failed a test vector.

    Args:
        test: The test's name (its fixture file's name).
        vector: The test vector (``players-4``, or ``default`` for a test with one).

    Returns:
        The seeds, oldest first (none when the test has no fixture yet).

    """
    path = FIXTURE_DIRECTORY / f'{test}.json'
    if not path.exists():
        return []
    seeds: dict[str, list[int]] = json.loads(path.read_text(encoding='utf-8'))
    return list(seeds.get(vector, []))


def seed_cases(*, test: str, vector: str = 'default') -> list[str | int]:
    """Return a test vector's seed cases: a fresh random one, then every saved seed.

    Returns:
        ``random``, then the saved seeds.

    """
    return [RANDOM_CASE, *saved_seeds(test=test, vector=vector)]


def resolve_seed(
    case: str | int, *, node: Any = None, test: str = '', vector: str = 'default'
) -> int:
    """Return a case's seed (a fresh one for ``random``, else the saved seed), recorded.

    Args:
        case: ``random`` or a saved seed.
        node: The running test (``request.node``): the seed is kept on it for the report.
        test: The test's fixture name.
        vector: The test vector.

    Returns:
        The seed.

    """
    # A fresh seed comes from the system (tests are outside the unseeded-randomness guard, which
    # scans gameplay source): it must differ from run to run
    seed = random.SystemRandom().randrange(SEED_LIMIT) if case == RANDOM_CASE else int(case)
    if node is not None:
        setattr(node, SEED_ATTRIBUTE, (seed, test, vector))
    return seed


def recorded_seed(node: Any) -> int | None:
    """Return the seed a running test resolved, if any.

    Returns:
        The seed, or None.

    """
    recorded = getattr(node, SEED_ATTRIBUTE, None)
    return None if recorded is None else recorded[0]


def seed_report(node: Any) -> str | None:
    """Return what a failed seeded test reports: its seed and where to save it.

    Returns:
        The note, or None for a test that took no seed.

    """
    recorded = getattr(node, SEED_ATTRIBUTE, None)
    if recorded is None:
        return None
    seed, test, vector = recorded
    return failure_note(test=test or 'the test', vector=vector, seed=seed)


def failure_note(*, test: str, vector: str, seed: int) -> str:
    """Return what to do with a failing seed: where it is saved.

    Returns:
        The note, for an assertion message.

    """
    return (
        f'seed {seed}: save it under "{vector}" in '
        f'{FIXTURE_DIRECTORY.name}/{test}.json, and keep it once the fix is in'
    )
