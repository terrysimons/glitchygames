"""A Lawn Zombie in the yard: it shambles toward the nearest standing kid, and grabs.

Feature plan 5 (plans/2026-11-14-zombies-aint-my-neighbors-5-zombies.md), Task 4.
"""

from __future__ import annotations

import math

import pygame
import pytest

from zombies_aint_my_neighbors.kid import Kid, MirrorCache
from zombies_aint_my_neighbors.neighborhood import WALK_SPEED
from zombies_aint_my_neighbors.zombie import (
    GRAB_SECONDS,
    ZOMBIE_SPEED,
    Zombie,
    ZombieFacing,
    touches,
)

SIXTIETH = 1.0 / 60.0


@pytest.fixture
def cache() -> MirrorCache:
    """The scene's flip cache."""
    return MirrorCache()


def kid_at(cache: MirrorCache, x: float, y: float) -> Kid:
    """Return Dex standing at a place.

    Returns:
        The kid.

    """
    kid = Kid(look_name='dex', world_x=x, world_y=y, mirror_cache=cache, groups=None)
    kid.dt_tick(0.0)
    return kid


def zombie_at(cache: MirrorCache, x: float, y: float) -> Zombie:
    """Return a Lawn Zombie at a place.

    Returns:
        The zombie.

    """
    return Zombie(world_x=x, world_y=y, mirror_cache=cache, groups=None)


def shamble(zombie: Zombie, kids: list[Kid], *, seconds: float) -> None:
    """Let a zombie chase for some seconds at 60 frames a second."""
    for _ in range(round(seconds * 60)):
        zombie.chase(kids=kids, dt=SIXTIETH)
        zombie.dt_tick(SIXTIETH)


def test_a_zombie_shambles_toward_a_kid_at_zombie_speed(cache):
    """A second of chasing a kid to its right covers the zombie's speed."""
    zombie = zombie_at(cache, 100.0, 100.0)
    kid = kid_at(cache, 500.0, 100.0)

    shamble(zombie, [kid], seconds=1.0)

    assert zombie.world_x == pytest.approx(100.0 + ZOMBIE_SPEED, abs=1.0)
    assert zombie.world_y == pytest.approx(100.0)


def test_a_zombie_is_slower_than_a_kid():
    """The BOM: slower than a kid (a third of the walk)."""
    assert ZOMBIE_SPEED < WALK_SPEED / 2


def test_a_zombie_chases_the_nearest_standing_kid(cache):
    """Of two kids, the nearer; once that one is knocked out, the other."""
    zombie = zombie_at(cache, 100.0, 100.0)
    near = kid_at(cache, 160.0, 100.0)
    far = kid_at(cache, 100.0, 400.0)

    shamble(zombie, [near, far], seconds=0.25)
    assert zombie.facing is ZombieFacing.RIGHT

    near.knock_out()
    shamble(zombie, [near, far], seconds=0.25)
    assert zombie.facing is ZombieFacing.DOWN


def test_a_zombie_stands_when_no_kid_is_up(cache):
    """With every kid knocked out, the zombie holds still on walk frame 0 (its idle, BOM 5.1)."""
    zombie = zombie_at(cache, 100.0, 100.0)
    kid = kid_at(cache, 300.0, 100.0)
    kid.knock_out()

    shamble(zombie, [kid], seconds=0.5)

    assert (zombie.world_x, zombie.world_y) == (100.0, 100.0)
    assert zombie.current_frame == 0
    assert not zombie.is_playing


@pytest.mark.parametrize(
    ('kid_place', 'facing', 'animation'),
    [
        ((100.0, 300.0), ZombieFacing.DOWN, 'walk_down'),
        ((100.0, -200.0), ZombieFacing.UP, 'walk_up'),
        ((-200.0, 100.0), ZombieFacing.LEFT, 'walk_left'),
        ((400.0, 100.0), ZombieFacing.RIGHT, 'walk_left'),
    ],
)
def test_a_zombie_faces_the_way_it_shambles(cache, kid_place, facing, animation):
    """Four facings; right plays the left walk, mirrored."""
    zombie = zombie_at(cache, 100.0, 100.0)

    shamble(zombie, [kid_at(cache, *kid_place)], seconds=0.1)

    assert zombie.facing is facing
    assert zombie.current_animation == animation


def test_a_zombie_facing_right_shows_its_left_frame_mirrored(cache):
    """Right is left flipped, through the scene's cache, with the hitbox flipped."""
    zombie = zombie_at(cache, 100.0, 100.0)

    shamble(zombie, [kid_at(cache, 400.0, 100.0)], seconds=0.1)

    mirrored = pygame.transform.flip(zombie.drawn_frame_surface(), flip_x=True, flip_y=False)
    width, height = mirrored.get_size()
    assert all(
        zombie.image.get_at((x, y)) == mirrored.get_at((x, y))
        for y in range(height)
        for x in range(width)
    )
    assert zombie.hitbox_flip_x


def test_a_grab_plays_then_the_zombie_walks_on(cache):
    """The lunge and clamp (0.2 s), then the shamble again."""
    zombie = zombie_at(cache, 100.0, 100.0)
    kid = kid_at(cache, 100.0, 300.0)
    shamble(zombie, [kid], seconds=0.1)

    zombie.grab()
    zombie.dt_tick(0.0)
    assert zombie.current_animation == 'grab_down'

    shamble(zombie, [kid], seconds=GRAB_SECONDS + 0.05)
    assert zombie.current_animation == 'walk_down'


def test_a_grabbing_zombie_stands_still(cache):
    """While it grabs, the zombie does not move."""
    zombie = zombie_at(cache, 100.0, 100.0)
    kid = kid_at(cache, 100.0, 300.0)
    zombie.grab()
    before = (zombie.world_x, zombie.world_y)

    zombie.chase(kids=[kid], dt=SIXTIETH)

    assert (zombie.world_x, zombie.world_y) == before


def test_touching_means_the_hitboxes_meet_with_the_forgiveness_margin(cache):
    """Overlapping bodies touch; frames that only brush within the margin do not."""
    zombie = zombie_at(cache, 100.0, 100.0)
    overlapping = kid_at(cache, 110.0, 100.0)
    # Both bodies are 20 wide from x+6 (106-126 and 122-142): they overlap by 4 px, which the
    # 4 px margin on each side forgives
    brushing = kid_at(cache, 116.0, 100.0)
    apart = kid_at(cache, 300.0, 100.0)

    assert touches(zombie=zombie, kid=overlapping)
    assert not touches(zombie=zombie, kid=brushing)
    assert not touches(zombie=zombie, kid=apart)


def test_a_zombie_never_walks_faster_diagonally(cache):
    """Chasing diagonally covers the same distance a second."""
    zombie = zombie_at(cache, 100.0, 100.0)

    shamble(zombie, [kid_at(cache, 500.0, 500.0)], seconds=1.0)

    travelled = math.hypot(zombie.world_x - 100.0, zombie.world_y - 100.0)
    assert travelled == pytest.approx(ZOMBIE_SPEED, abs=1.0)
