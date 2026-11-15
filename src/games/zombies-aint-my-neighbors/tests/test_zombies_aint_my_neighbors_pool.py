"""A pool of sprites built before play and reused, so nothing loads a sprite file mid-game.

Master plan decision 11 (heavy work before play): each zombie's and zap's sprite file took
27 to 41 ms and about 2 ms to load (measured 2026-11-15), so the neighborhood builds them ahead.
"""

from __future__ import annotations

import logging

from zombies_aint_my_neighbors.pool import SpritePool


class Made:
    """A stand-in sprite: counts how many were made."""

    made = 0

    def __init__(self) -> None:
        """Count one more."""
        Made.made += 1


def fresh_pool(size: int) -> SpritePool[Made]:
    """Return a pool of ``size`` stand-ins, the count started from zero.

    Returns:
        The pool.

    """
    Made.made = 0
    return SpritePool(make=Made, size=size)


def test_a_pool_builds_its_sprites_up_front():
    """All of them, when it is made."""
    pool = fresh_pool(3)

    assert Made.made == 3
    assert pool.free == pool.size == 3


def test_taking_never_makes_a_sprite_while_any_are_free():
    """Three taken from three: none made."""
    pool = fresh_pool(3)

    taken = [pool.take() for _ in range(3)]

    assert Made.made == 3
    assert len(set(map(id, taken))) == 3


def test_a_sprite_given_back_is_taken_again():
    """Reuse, not a new one."""
    pool = fresh_pool(1)
    sprite = pool.take()

    pool.give_back(sprite)

    assert pool.take() is sprite
    assert pool.given_back == 1


def test_an_empty_pool_makes_one_and_says_so(caplog):
    """Running dry still works, but logs a warning: the pool's size was too small."""
    pool = fresh_pool(1)
    pool.take()

    with caplog.at_level(logging.WARNING):
        pool.take()

    assert Made.made == 2
    assert 'pool' in caplog.text
