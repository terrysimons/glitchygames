"""A zap from the Channel Changer: its flight, its range, its fizzle, the yard's edge, its hits.

Feature plan 6 (plans/2026-11-15-zombies-aint-my-neighbors-6-channel-changer.md), Task 6: a ring
of static at 320 px/s for at most 0.6 s (192 px), then a 2-frame fizzle (0.12 s) and gone; it
fizzles at the yard's edge; the first zombie or TV it touches takes the hit and the zap is gone.
"""

from __future__ import annotations

import math

import pygame
import pytest

from zombies_aint_my_neighbors.kid import MirrorCache
from zombies_aint_my_neighbors.zap import (
    FIZZLE_SECONDS,
    ZAP_RANGE_SECONDS,
    ZAP_SIZE,
    ZAP_SPEED,
    Zap,
    ZapState,
    first_struck,
)
from zombies_aint_my_neighbors.zombie import Zombie

SIXTIETH_OF_A_SECOND = 1.0 / 60.0
YARD = pygame.Rect(0, 0, 1600, 960)


def make_zap(*, centre=(400.0, 300.0), direction=(1.0, 0.0), groups=None) -> Zap:
    """Return a zap leaving ``centre`` toward ``direction``, in the yard.

    Returns:
        The zap.

    """
    return Zap(centre=centre, direction=direction, bounds=YARD, groups=groups)


def tick(zap: Zap, *, frames: int) -> None:
    """Tick a zap ``frames`` sixtieths of a second."""
    for _ in range(frames):
        zap.dt_tick(SIXTIETH_OF_A_SECOND)


def test_the_plan_values():
    """320 px/s, 0.6 s, a 0.12 s fizzle, 12 px across."""
    assert (ZAP_SPEED, ZAP_RANGE_SECONDS, FIZZLE_SECONDS, ZAP_SIZE) == (320.0, 0.6, 0.12, 12)


def test_a_zap_starts_centred_on_the_muzzle():
    """Its 12x12 frame's centre is where it leaves."""
    zap = make_zap(centre=(400.0, 300.0))

    assert zap.centre() == (400.0, 300.0)
    assert (zap.world_x, zap.world_y) == (394.0, 294.0)


@pytest.mark.parametrize('direction', [(1.0, 0.0), (0.0, -1.0), (-math.sqrt(0.5), math.sqrt(0.5))])
def test_a_zap_flies_its_direction_at_its_speed(direction):
    """A quarter second covers 80 px, along the aim."""
    zap = make_zap(direction=direction)

    tick(zap, frames=15)

    centre_x, centre_y = zap.centre()
    assert centre_x == pytest.approx(400.0 + direction[0] * 80.0)
    assert centre_y == pytest.approx(300.0 + direction[1] * 80.0)
    assert zap.state is ZapState.FLYING
    assert zap.current_animation == 'fly'


def test_a_zap_fizzles_at_its_range_on_its_exact_frame():
    """36 frames (0.6 s) out it fizzles where it is, 192 px from the muzzle, and stops."""
    zap = make_zap()

    tick(zap, frames=35)
    assert zap.state is ZapState.FLYING
    tick(zap, frames=1)

    assert zap.state is ZapState.FIZZLING
    assert zap.current_animation == 'fizzle'
    assert zap.centre()[0] == pytest.approx(400.0 + 192.0)
    tick(zap, frames=3)
    assert zap.centre()[0] == pytest.approx(400.0 + 192.0)


def test_a_fizzled_zap_is_gone_after_its_two_frames():
    """The fizzle lasts 0.12 s (8 sixtieths reach it: 7.2 rounded up), then the zap is gone.

    Gone is hidden, still in its group: the scene's pool reuses it, and a removed sprite must not
    be held (tests/replay/test_removed_sprites_are_freed.py).
    """
    group = pygame.sprite.LayeredDirty()
    zap = make_zap(groups=group)
    tick(zap, frames=36)

    tick(zap, frames=math.ceil(FIZZLE_SECONDS / SIXTIETH_OF_A_SECOND) - 1)
    assert not zap.hidden
    tick(zap, frames=1)

    assert zap.state is ZapState.GONE
    assert zap.hidden
    assert zap.alive()


def test_a_zap_fizzles_at_the_yards_edge():
    """A zap whose centre leaves the yard fizzles there, short of its range."""
    zap = make_zap(centre=(1590.0, 300.0))

    tick(zap, frames=3)

    assert zap.state is ZapState.FIZZLING
    assert zap.centre()[0] <= YARD.right


def test_a_struck_zap_is_gone_at_once():
    """It hits and vanishes (hidden, kept for its pool): no fizzle."""
    group = pygame.sprite.LayeredDirty()
    zap = make_zap(groups=group)

    zap.strike()

    assert zap.state is ZapState.GONE
    assert zap.hidden


def test_only_a_flying_zap_can_strike():
    """A fizzling zap passes through everything (after the frame its flight ends on)."""
    zap = make_zap()
    tick(zap, frames=37)

    assert not zap.is_live


def zombie_at(world_x: float, world_y: float) -> Zombie:
    """Return a zombie standing with its frame's top-left at a place.

    Returns:
        The zombie.

    """
    zombie = Zombie(world_x=world_x, world_y=world_y, mirror_cache=MirrorCache(), groups=None)
    zombie.dt_tick(0.0)
    return zombie


def test_a_zap_strikes_a_zombie_it_touches():
    """The zap's 8x8 hitbox meeting a zombie's body hitbox is a hit."""
    zombie = zombie_at(400.0, 270.0)
    zap = make_zap(centre=(416.0, 300.0))

    assert first_struck(zap=zap, targets=[zombie]) is zombie


def test_a_zap_misses_what_it_does_not_touch():
    """Beside the hitbox (inside the frame's transparent margin) is a miss."""
    zombie = zombie_at(400.0, 270.0)
    # The body hitbox spans x 406..426; the zap's spans 6 px either side of x 400
    zap = make_zap(centre=(399.0, 300.0))

    assert first_struck(zap=zap, targets=[zombie]) is None


def test_a_zap_touching_two_strikes_the_nearer():
    """Only one target takes the hit: the one whose hitbox centre is nearest the zap's."""
    near = zombie_at(400.0, 270.0)
    far = zombie_at(408.0, 270.0)
    zap = make_zap(centre=(414.0, 300.0))

    assert first_struck(zap=zap, targets=[far, near]) is near


def test_a_zap_strikes_what_it_meets_on_its_last_step():
    """A zombie reachable only in the step that ends the zap's range is still struck."""
    zap = make_zap(centre=(400.0, 300.0))
    # At 192 px the zap's hitbox reaches x 596; a step earlier, about 590.7. The zombie's body
    # hitbox starts 6 px into its frame, so its frame at 588 puts the hitbox's edge at 594
    zombie = zombie_at(588.0, 270.0)
    tick(zap, frames=35)
    assert first_struck(zap=zap, targets=[zombie]) is None

    tick(zap, frames=1)

    assert first_struck(zap=zap, targets=[zombie]) is zombie


def test_a_zap_strikes_what_it_meets_at_the_yards_edge():
    """A target at the yard's edge is struck on the step that stops the zap there."""
    zap = make_zap(centre=(1590.0, 300.0))
    zombie = zombie_at(1580.0, 270.0)
    zombie.world_x = 1600.0 - 6 - 20 + 2

    # 5.3 px a frame: the second frame would carry the centre past 1600
    tick(zap, frames=2)

    assert zap.state is ZapState.FIZZLING
    assert first_struck(zap=zap, targets=[zombie]) is zombie


def test_a_spent_zap_launched_again_flies_fresh():
    """Reused from the pool: flying from its new muzzle, its new way, its range renewed."""
    zap = make_zap()
    zap.strike()

    zap.launch(centre=(100.0, 200.0), direction=(0.0, -1.0))
    tick(zap, frames=15)

    assert zap.state is ZapState.FLYING
    assert not zap.hidden
    assert zap.current_animation == 'fly'
    assert zap.centre() == pytest.approx((100.0, 200.0 - 80.0))


# The neighborhood caps a frame at 0.05 s (MAX_FRAME_SECONDS), so a zap's step stays shorter
# than its hitbox and a zombie's together: it can never pass through one between two tests
NARROWEST_TARGET_HITBOX = 20
ZAP_HITBOX = 8


def test_the_neighborhoods_frame_cap_keeps_a_zap_from_stepping_over_a_zombie():
    """320 px/s for at most 0.05 s is 16 px, under 8 + 20."""
    from zombies_aint_my_neighbors.neighborhood import NeighborhoodScene

    cap = NeighborhoodScene.MAX_FRAME_SECONDS
    assert cap == 0.05
    assert cap is not None
    assert ZAP_SPEED * cap < ZAP_HITBOX + NARROWEST_TARGET_HITBOX


@pytest.mark.parametrize('offset', range(40))
def test_at_the_capped_frame_a_zap_never_passes_through_a_zombie_ahead(offset):
    """Every start, 0.05 s frames: the zap strikes the zombie dead ahead, within its range."""
    # The body hitbox spans x 456 to 476: in reach of every start (192 px, plus 4 px of hitbox)
    zombie = zombie_at(450.0, 270.0)
    zap = make_zap(centre=(300.0 + offset, 300.0))
    struck = None
    for _ in range(round(ZAP_RANGE_SECONDS / 0.05)):
        zap.dt_tick(0.05)
        struck = first_struck(zap=zap, targets=[zombie])
        if struck is not None:
            break

    assert struck is zombie
