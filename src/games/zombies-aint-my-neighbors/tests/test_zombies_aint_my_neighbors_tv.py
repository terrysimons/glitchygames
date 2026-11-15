"""A TV in the yard: static, and a Lawn Zombie popping out every 6 to 9 seconds.

Feature plan 5 (plans/2026-11-14-zombies-aint-my-neighbors-5-zombies.md), Task 5; the props
BOM's TV (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md).
"""

from __future__ import annotations

import math
import random

import pytest

from zombies_aint_my_neighbors.tv import (
    POP_SECONDS,
    SPAWN_MAXIMUM_SECONDS,
    SPAWN_MINIMUM_SECONDS,
    SPAWN_SECONDS,
    ZOMBIES_IN_ALL,
    ZOMBIES_PER_TV,
    Tv,
    may_spawn,
)

SIXTIETH = 1.0 / 60.0
# A minute of frames: every wait is at most 9 s, so a TV that has not acted by then never will
FRAME_LIMIT = 60 * 60


def tv_with_seed(seed: int) -> Tv:
    """Return a TV at (200, 300) drawing its timings from a seeded stream.

    Returns:
        The TV.

    """
    return Tv(world_x=200.0, world_y=300.0, stream=random.Random(seed), groups=None)


def frames_until_spawn_starts(tv: Tv) -> int:
    """Tick a TV (spawning allowed) until its spawn starts, returning the frames ticked.

    Returns:
        The frames.

    """
    for frames in range(FRAME_LIMIT):
        if tv.is_spawning:
            return frames
        tick(tv)
    pytest.fail('the TV never started a spawn')


def finish_spawn(tv: Tv) -> None:
    """Tick a TV until its spawn ends, failing at the limit."""
    for _ in range(FRAME_LIMIT):
        if not tv.is_spawning:
            return
        tick(tv)
    pytest.fail('the spawn never ended')


def tick(tv: Tv, *, allowed: bool = True) -> bool:
    """Tick a TV one frame: its spawning, then its pose.

    Returns:
        Whether a zombie is due this frame.

    """
    due = tv.tick_spawning(dt=SIXTIETH, allowed=allowed)
    tv.dt_tick(SIXTIETH)
    return due


def test_the_props_bom_timings():
    """The pop ends with spawn frame 2 (3 frames of 0.08 s); the spawn lasts 4."""
    assert math.isclose(POP_SECONDS, 0.24)
    assert math.isclose(SPAWN_SECONDS, 0.32)


def test_the_caps_are_the_plans():
    """Three zombies alive per TV, ten in all (feature plan 5)."""
    assert (ZOMBIES_PER_TV, ZOMBIES_IN_ALL) == (3, 10)


@pytest.mark.parametrize('seed', range(40))
def test_each_spawn_waits_6_to_9_seconds(seed):
    """The first wait, and each after it, falls within 6 to 9 s."""
    tv = tv_with_seed(seed)
    for _ in range(3):
        frames = frames_until_spawn_starts(tv)
        assert SPAWN_MINIMUM_SECONDS * 60 <= frames <= SPAWN_MAXIMUM_SECONDS * 60 + 1
        finish_spawn(tv)


def test_the_waits_vary():
    """Different seeds wait different times (the stream is used, not a constant)."""
    waits = {frames_until_spawn_starts(tv_with_seed(seed)) for seed in range(10)}

    assert len(waits) > 1


def test_the_same_seed_spawns_at_the_same_frames():
    """A replay repeats the timings: two TVs on equal streams spawn on equal frames."""
    first, second = tv_with_seed(7), tv_with_seed(7)

    assert spawn_frames(first, spawns=3) == spawn_frames(second, spawns=3)


def spawn_frames(tv: Tv, *, spawns: int) -> list[int]:
    """Return the frames on which a TV's spawns start, counting from its first frame.

    Returns:
        The frames.

    """
    frames: list[int] = []
    for frame in range(1, FRAME_LIMIT + 1):
        was_spawning = tv.is_spawning
        tick(tv)
        if tv.is_spawning and not was_spawning:
            frames.append(frame)
            if len(frames) == spawns:
                return frames
    pytest.fail(f'only {len(frames)} spawns started')


def test_a_tv_shows_static_until_it_spawns():
    """Static loops while waiting."""
    tv = tv_with_seed(1)
    for _ in range(60):
        tv.tick_spawning(dt=SIXTIETH, allowed=True)
        tv.dt_tick(SIXTIETH)

    assert tv.current_animation == 'static'
    assert tv.is_playing


def test_a_zombie_appears_after_the_pop_once():
    """The spawn plays; the zombie is due on the frame the pop ends, and only then."""
    tv = tv_with_seed(2)
    frames_until_spawn_starts(tv)
    assert tv.current_animation == 'spawn'
    assert tv.zombies == 1

    due = []
    for frame in range(1, round(SPAWN_SECONDS * 60) + 5):
        if tv.tick_spawning(dt=SIXTIETH, allowed=True):
            due.append(frame)
        tv.dt_tick(SIXTIETH)

    # The first frame at or past 0.24 s: the 15th (14 frames are 0.233 s)
    assert due == [math.ceil(POP_SECONDS * 60)]


def test_after_the_spawn_the_tv_shows_static_again():
    """The spawn's 4 frames, then static."""
    tv = tv_with_seed(3)
    frames_until_spawn_starts(tv)
    for _ in range(round(SPAWN_SECONDS * 60) + 1):
        tv.tick_spawning(dt=SIXTIETH, allowed=True)
        tv.dt_tick(SIXTIETH)

    assert not tv.is_spawning
    assert tv.current_animation == 'static'


def test_a_capped_tv_skips_its_spawn_and_waits_again():
    """When spawning is not allowed as the wait runs out, nothing spawns and a new wait starts."""
    tv = tv_with_seed(4)
    for _ in range(round(SPAWN_MAXIMUM_SECONDS * 60) + 2):
        tv.tick_spawning(dt=SIXTIETH, allowed=False)
        tv.dt_tick(SIXTIETH)

    assert not tv.is_spawning
    assert tv.zombies == 0
    assert tv.current_animation == 'static'
    assert tv.seconds_until_spawn > 0


@pytest.mark.parametrize(
    ('this_tv', 'all_tvs', 'expected'),
    [
        (0, 0, True),
        (2, 9, True),
        (3, 3, False),
        (0, 10, False),
        (1, 10, False),
    ],
)
def test_may_spawn_keeps_both_caps(this_tv, all_tvs, expected):
    """Below three for this TV and below ten in all."""
    assert may_spawn(zombies_from_this_tv=this_tv, zombies_in_all=all_tvs) is expected


def test_the_zombie_stands_in_front_of_its_tv_centred():
    """Centred on the TV, its feet just below the TV's (in front, by the depth rule)."""
    tv = tv_with_seed(5)

    zombie_x, zombie_y = tv.spawn_point()

    assert zombie_x + 32 / 2 == pytest.approx(tv.world_x + 48 / 2)
    assert zombie_y + 48 > tv.world_y + 48
