"""The engine's random number source, seeded once per run so a run can be repeated.

``GameEngine`` seeds it at startup with ``seed_engine_random()``: from ``--random-seed <int>``
when given, otherwise from ``secrets.randbits(SEED_BITS)``. The seed is kept
(``engine_random_seed()``, ``GameEngine.random_seed``) and written to the header of a
``--record-trace`` recording.

Replaying a recording exactly (the planned ``--replay-trace``, see ``plans/future-work.md``)
needs every random number that affects the simulation to come from ``engine_random()``: not
from the ``random`` module's global functions, ``secrets``, ``random.SystemRandom`` or a
game's own ``random.Random``. The example games have not been moved onto it yet; until they
are, a recording's seed does not make their randomness repeat.
"""

from __future__ import annotations

import dataclasses
import random
import secrets

# Bits drawn from secrets when no seed is given
SEED_BITS = 64


@dataclasses.dataclass
class EngineRandomState:
    """The current seed and the generator seeded with it (both None until first seeded)."""

    seed: int | None = None
    generator: random.Random | None = None


_STATE = EngineRandomState()


def seed_engine_random(*, seed: int | None = None) -> int:
    """Start a new engine random generator.

    Args:
        seed: The seed, or None to draw one from ``secrets.randbits(SEED_BITS)``.

    Returns:
        The seed used.

    """
    chosen_seed = secrets.randbits(SEED_BITS) if seed is None else seed
    _STATE.seed = chosen_seed
    _STATE.generator = random.Random(chosen_seed)
    return chosen_seed


def engine_random() -> random.Random:
    """Return the engine's random generator, seeding it from secrets if nothing has yet.

    Returns:
        The generator every simulation-affecting random number should come from.

    """
    if _STATE.generator is None:
        seed_engine_random()
    generator = _STATE.generator
    assert generator is not None
    return generator


def engine_random_seed() -> int:
    """Return the seed of the current engine random generator (seeding it if needed).

    Returns:
        The seed.

    """
    engine_random()
    seed = _STATE.seed
    assert seed is not None
    return seed
