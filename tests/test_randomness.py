"""Tests for the engine's random number source (glitchygames/randomness.py)."""

from __future__ import annotations

import random

import pytest

from glitchygames import randomness
from glitchygames.randomness import (
    SEED_BITS,
    engine_random,
    engine_random_seed,
    seed_engine_random,
)

DRAW_COUNT = 20


@pytest.fixture(autouse=True)
def fresh_engine_random(mocker):
    """Give each test an unseeded engine random source, restored afterwards."""
    mocker.patch.object(randomness, '_STATE', randomness.EngineRandomState())


def _draws() -> list[float]:
    return [engine_random().random() for _ in range(DRAW_COUNT)]


def test_same_seed_gives_the_same_numbers():
    """Two runs seeded with 123 draw the same sequence."""
    assert seed_engine_random(seed=123) == 123
    first_run = _draws()
    seed_engine_random(seed=123)
    second_run = _draws()

    reference_generator = random.Random(123)
    assert first_run == second_run
    assert first_run == [reference_generator.random() for _ in range(DRAW_COUNT)]


def test_different_seeds_give_different_numbers():
    """Seeds 123 and 124 draw different sequences."""
    seed_engine_random(seed=123)
    first_run = _draws()
    seed_engine_random(seed=124)

    assert _draws() != first_run


def test_no_seed_draws_one_from_secrets(mocker):
    """Without a seed, the seed is secrets.randbits(SEED_BITS) and is remembered."""
    randbits = mocker.patch.object(randomness.secrets, 'randbits', return_value=987654321)

    assert seed_engine_random() == 987654321
    randbits.assert_called_once_with(SEED_BITS)
    assert engine_random_seed() == 987654321
    assert engine_random().random() == random.Random(987654321).random()


def test_engine_random_seeds_itself_on_first_use(mocker):
    """A game that draws before the engine seeded gets a secrets-seeded source, not None."""
    mocker.patch.object(randomness.secrets, 'randbits', return_value=42)

    generator = engine_random()

    assert generator is engine_random()
    assert engine_random_seed() == 42


def test_reseeding_replaces_the_generator():
    """Each seeding starts a new generator; a stale reference is not reseeded."""
    seed_engine_random(seed=1)
    old_generator = engine_random()
    seed_engine_random(seed=1)

    assert engine_random() is not old_generator
    assert engine_random_seed() == 1
