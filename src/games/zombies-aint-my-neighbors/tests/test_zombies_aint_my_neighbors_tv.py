"""A TV in the yard: static, and a Lawn Zombie popping out every 6 to 9 seconds.

Feature plan 5 (plans/2026-11-14-zombies-aint-my-neighbors-5-zombies.md), Task 5; the props
BOM's TV (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md).
"""

from __future__ import annotations

import math
import random

import pygame
import pytest

from glitchygames.randomness import capture_stream_states, reset_streams
from zombies_aint_my_neighbors.tv import (
    HITS_PER_STAGE,
    POP_SECONDS,
    SPAWN_MAXIMUM_SECONDS,
    SPAWN_MINIMUM_SECONDS,
    SPAWN_SECONDS,
    ZOMBIES_IN_ALL,
    ZOMBIES_PER_TV,
    Tv,
    TvHit,
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
    tv = Tv(groups=None)
    tv.place(world_x=200.0, world_y=300.0, stream=random.Random(seed))
    return tv


def test_a_tv_draws_its_first_wait_when_placed_not_when_built():
    """Built ahead on the stage card, a TV draws nothing until its stage places it (plan 9)."""
    stream = random.Random(3)
    reset_streams(seed=3)
    before = capture_stream_states()
    tv = Tv(groups=None)
    assert capture_stream_states() == before

    tv.place(world_x=40.0, world_y=50.0, stream=stream)

    assert (tv.world_x, tv.world_y) == (40.0, 50.0)
    expected = random.Random(3).uniform(SPAWN_MINIMUM_SECONDS, SPAWN_MAXIMUM_SECONDS)
    assert tv.seconds_until_spawn == pytest.approx(expected)


def test_a_tv_never_placed_refuses_to_draw_a_wait():
    """Due to spawn with no stream (never placed), a TV fails loudly instead of guessing."""
    tv = Tv(groups=None)
    tv.seconds_until_spawn = 0.0

    with pytest.raises(RuntimeError, match='placed'):
        tv.tick_spawning(dt=SIXTIETH, allowed=True)


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


# Damage (feature plan 6): 3 zaps a stage, intact -> cracked -> smashed -> destroyed; each stage
# doubles the wait between spawns; a destroyed TV spawns nothing; a started spawn finishes


def zap_times(tv: Tv, times: int) -> list[TvHit]:
    """Zap a TV ``times`` times, returning each hit's result.

    Returns:
        The results.

    """
    return [tv.zap() for _ in range(times)]


def test_three_zaps_break_a_tv_into_its_next_stage():
    """Two hits mark it; the third breaks it to the next stage."""
    tv = tv_with_seed(1)

    assert zap_times(tv, 3) == [TvHit.HIT, TvHit.HIT, TvHit.BROKE]
    assert tv.stage == 'cracked'


def test_nine_zaps_destroy_a_tv_and_more_pass_by():
    """Cracked at 3, smashed at 6, destroyed at 9; a destroyed TV takes no more hits."""
    tv = tv_with_seed(1)

    results = zap_times(tv, 10)

    assert results[2] == results[5] == TvHit.BROKE
    assert results[8] == TvHit.DESTROYED
    assert results[9] == TvHit.MISSED
    assert tv.stage == 'destroyed'
    assert tv.is_destroyed
    assert HITS_PER_STAGE == 3


@pytest.mark.parametrize(
    ('zaps', 'animation'),
    [(0, 'static'), (3, 'cracked-static'), (6, 'smashed-static'), (9, 'destroyed')],
)
def test_each_stage_shows_its_own_static(zaps, animation):
    """The TV's animation follows its stage."""
    tv = tv_with_seed(1)
    zap_times(tv, zaps)

    tick(tv)

    assert tv.current_animation == animation


@pytest.mark.parametrize(('zaps', 'animation'), [(3, 'cracked-spawn'), (6, 'smashed-spawn')])
def test_a_damaged_tv_spawns_with_its_stages_spawn(zaps, animation):
    """A cracked or smashed TV's spawn is its own stage's."""
    tv = tv_with_seed(1)
    zap_times(tv, zaps)

    frames_until_spawn_starts(tv)
    tick(tv)

    assert tv.current_animation == animation


@pytest.mark.parametrize(('zaps', 'factor'), [(0, 1), (3, 2), (6, 4)])
def test_each_stage_doubles_the_wait(zaps, factor):
    """The same stream's first wait, doubled at each stage: 6-9 s, then 12-18 s, then 24-36 s."""
    intact = tv_with_seed(7)
    damaged = tv_with_seed(7)
    zap_times(damaged, zaps)

    assert damaged.seconds_until_spawn == pytest.approx(intact.seconds_until_spawn * factor)


def test_the_next_waits_are_doubled_too():
    """After a cracked TV's spawn, its next wait is drawn and doubled."""
    intact = tv_with_seed(7)
    cracked = tv_with_seed(7)
    zap_times(cracked, 3)
    frames_until_spawn_starts(intact)
    frames_until_spawn_starts(cracked)

    assert cracked.seconds_until_spawn == pytest.approx(intact.seconds_until_spawn * 2)


def test_a_destroyed_tv_never_spawns():
    """A minute of frames, no spawn and no zombie due."""
    tv = tv_with_seed(1)
    zap_times(tv, 9)

    assert not any(tick(tv) for _ in range(FRAME_LIMIT))
    assert not tv.is_spawning


def test_a_spawn_already_started_finishes_when_the_tv_is_destroyed():
    """Destroyed mid-spawn, the zombie still comes out."""
    tv = tv_with_seed(1)
    zap_times(tv, 8)
    frames_until_spawn_starts(tv)
    tv.zap()

    assert any(tick(tv) for _ in range(round(POP_SECONDS / SIXTIETH) + 1))


def test_a_zapped_tv_flashes_white_for_its_flash_time():
    """Its drawn pixels go white for 0.05 s, then it shows its frame again."""
    tv = tv_with_seed(1)
    tick(tv)
    tv.zap()
    tick(tv)
    frame = tv.drawn_frame_surface()
    mask = pygame.mask.from_surface(frame)
    drawn = next(
        (x, y)
        for y in range(frame.get_height())
        for x in range(frame.get_width())
        if mask.get_at((x, y))
    )

    assert tuple(tv.image.get_at(drawn))[:3] == (255, 255, 255)
    tick(tv)
    tick(tv)
    assert tv.image is tv.drawn_frame_surface()


def test_a_zombie_leaving_frees_its_place_under_the_caps():
    """When one of its zombies dies, the TV counts one fewer (never below none)."""
    tv = tv_with_seed(1)
    tv.zombies = 2

    tv.zombie_left()
    tv.zombie_left()
    tv.zombie_left()

    assert tv.zombies == 0


def test_a_tv_broken_mid_spawn_carries_its_spawn_on_from_the_same_frame():
    """Cracked partway through a spawn, it plays the cracked spawn from where it had got to."""
    tv = tv_with_seed(1)
    zap_times(tv, HITS_PER_STAGE - 1)
    frames_until_spawn_starts(tv)
    for _ in range(FRAME_LIMIT):
        tick(tv)
        if tv.current_frame > 0:
            break
    reached = tv.current_frame
    assert tv.current_animation == 'spawn'
    assert reached > 0

    tv.zap()
    tick(tv)

    assert tv.current_animation == 'cracked-spawn'
    assert tv.current_frame == reached


def test_a_tv_destroyed_mid_spawn_plays_the_spawn_out_then_smokes():
    """Its zombie comes out of a spawn you can see; the smoke follows when the spawn ends."""
    tv = tv_with_seed(1)
    zap_times(tv, 8)
    frames_until_spawn_starts(tv)
    tick(tv)
    tv.zap()
    tick(tv)

    assert tv.is_destroyed
    assert tv.current_animation == 'smashed-spawn'
    finish_spawn(tv)
    tick(tv)
    assert tv.current_animation == 'destroyed'
