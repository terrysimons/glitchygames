"""When a zombie groans: sometimes, at a new target, never too often (feature plan 10)."""

from __future__ import annotations

import itertools

import pytest

from zombies_aint_my_neighbors.groans import (
    GROAN_CHANCE,
    GROAN_REST_SECONDS,
    GROAN_SPACING_SECONDS,
    GroanTimer,
)

LUCKY = GROAN_CHANCE - 0.01
UNLUCKY = GROAN_CHANCE


class Rolls:
    """Rolls handed out in order, counting how many were asked for."""

    def __init__(self, *values: float) -> None:
        """Hand these out, in order."""
        self._values = iter(values)
        self.asked = 0

    def __call__(self) -> float:
        """Return the next roll.

        Returns:
            It.

        """
        self.asked += 1
        return next(self._values)


def test_the_plan_values():
    """One time in three, a zombie's rest of 3 s, half a second between any two groans."""
    assert (
        pytest.approx(1 / 3),
        3.0,
        0.5,
    ) == (GROAN_CHANCE, GROAN_REST_SECONDS, GROAN_SPACING_SECONDS)


def test_a_lucky_roll_groans():
    """A new target and a roll under the chance: it groans."""
    assert GroanTimer().should_groan(zombie='a', now=10.0, roll=Rolls(LUCKY))


def test_an_unlucky_roll_stays_quiet_and_costs_no_rest():
    """A roll at or over the chance: silence, and the zombie may groan at its next new target."""
    timer = GroanTimer()

    assert not timer.should_groan(zombie='a', now=10.0, roll=Rolls(UNLUCKY))
    assert timer.should_groan(zombie='a', now=10.1, roll=Rolls(LUCKY))


def test_a_zombie_rests_after_groaning():
    """Within 3 s of its own groan it stays quiet, without even rolling."""
    timer = GroanTimer()
    timer.should_groan(zombie='a', now=10.0, roll=Rolls(LUCKY))
    rolls = Rolls(LUCKY)

    assert not timer.should_groan(zombie='a', now=10.0 + GROAN_REST_SECONDS - 0.1, roll=rolls)
    assert rolls.asked == 0
    assert timer.should_groan(zombie='a', now=10.0 + GROAN_REST_SECONDS, roll=Rolls(LUCKY))


def test_no_two_groans_start_within_half_a_second():
    """Another zombie's groan just began: this one waits its turn (a crowd never moans at once)."""
    timer = GroanTimer()
    timer.should_groan(zombie='a', now=10.0, roll=Rolls(LUCKY))
    rolls = Rolls(LUCKY)

    assert not timer.should_groan(zombie='b', now=10.0 + GROAN_SPACING_SECONDS - 0.1, roll=rolls)
    assert rolls.asked == 0
    assert timer.should_groan(zombie='b', now=10.0 + GROAN_SPACING_SECONDS, roll=Rolls(LUCKY))


def test_a_crowd_seeing_kids_at_once_groans_once_each_half_second_at_most():
    """Sixteen zombies with new targets every frame for 3 s, every roll lucky: six groans."""
    timer = GroanTimer()
    groans = 0
    for frame, zombie in itertools.product(range(180), range(16)):
        groans += timer.should_groan(zombie=zombie, now=frame / 60, roll=Rolls(LUCKY))

    assert groans == 6
