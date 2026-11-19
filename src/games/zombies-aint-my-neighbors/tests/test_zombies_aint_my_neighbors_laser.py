"""The laser pointer's battery: 3 s of shine, a slow refill, dead until a third full.

Feature plan 8, Task 4: shining drains 1 s a second from a full 3.0 s; not shining refills at
0.3 s a second (10 s from empty); run flat, it stays dead until refilled to 1.0 s.
"""

from __future__ import annotations

import pytest

from zombies_aint_my_neighbors.laser import (
    FULL_SECONDS,
    RECHARGE_PER_SECOND,
    REVIVE_SECONDS,
    LaserBattery,
)

SIXTIETH = 1.0 / 60.0


def lit_frames(battery: LaserBattery, *, frames: int, held: bool = True) -> int:
    """Tick a battery some sixtieths with the trigger held or not; count the frames it shone.

    Returns:
        The frames lit.

    """
    return sum(battery.tick(dt=SIXTIETH, wants_light=held) for _ in range(frames))


def test_the_plan_values():
    """3 s, 0.3 s a second, alive again at 1 s."""
    assert (FULL_SECONDS, RECHARGE_PER_SECOND, REVIVE_SECONDS) == (3.0, 0.3, 1.0)


def test_a_full_battery_shines_exactly_three_seconds():
    """180 frames lit, then dark however long the trigger is held."""
    battery = LaserBattery()

    assert lit_frames(battery, frames=180) == 180
    assert battery.is_dead
    assert lit_frames(battery, frames=60) == 0


def test_releasing_keeps_the_charge_left():
    """A second of shine leaves two; the next press shines two more."""
    battery = LaserBattery()
    lit_frames(battery, frames=60)
    battery.tick(dt=0.0, wants_light=False)

    assert battery.charge_seconds == pytest.approx(2.0)
    assert lit_frames(battery, frames=200) == 120


def test_a_dead_battery_wakes_at_a_third_full_on_its_exact_frame():
    """Run flat, it refills 0.3 s a second: 1.0 s after 200 frames, and lights then."""
    battery = LaserBattery()
    lit_frames(battery, frames=180)

    assert lit_frames(battery, frames=199, held=False) == 0
    assert battery.is_dead
    assert lit_frames(battery, frames=1, held=False) == 0
    assert not battery.is_dead
    assert battery.tick(dt=SIXTIETH, wants_light=True)


def test_holding_the_trigger_on_a_dead_battery_still_refills_it():
    """Dead, it refills whether or not the trigger is held, and lights as soon as it wakes."""
    battery = LaserBattery()
    lit_frames(battery, frames=180)

    lit = [battery.tick(dt=SIXTIETH, wants_light=True) for _ in range(201)]

    assert lit[:200] == [False] * 200
    assert lit[200]


def test_a_flat_battery_refills_in_ten_seconds_and_no_further():
    """600 frames from empty to full; it never passes full."""
    battery = LaserBattery()
    lit_frames(battery, frames=180)

    lit_frames(battery, frames=600, held=False)
    assert battery.charge_seconds == pytest.approx(FULL_SECONDS)
    lit_frames(battery, frames=600, held=False)
    assert battery.charge_seconds == pytest.approx(FULL_SECONDS)


def test_the_fraction_left_for_the_display():
    """Full is 1, half is 0.5, empty is 0."""
    battery = LaserBattery()
    assert battery.fraction == pytest.approx(1.0)
    lit_frames(battery, frames=90)
    assert battery.fraction == pytest.approx(0.5)
    lit_frames(battery, frames=90)
    assert battery.fraction == pytest.approx(0.0)
