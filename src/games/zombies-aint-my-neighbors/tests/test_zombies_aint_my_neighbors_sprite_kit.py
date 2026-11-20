"""The sprite kit: the next stage's sprites, built ahead and each used once.

Feature plan 9 (plans/2026-11-15-zombies-aint-my-neighbors-9-sprite-kit.md).
"""

from __future__ import annotations

from collections import Counter

import pygame
import pytest

from glitchygames.randomness import capture_stream_states, random_stream, reset_streams
from glitchygames.sprites import AnimatedSprite
from zombies_aint_my_neighbors import sprite_kit
from zombies_aint_my_neighbors.kid import Kid
from zombies_aint_my_neighbors.neighbor import Neighbor, NeighborEffect
from zombies_aint_my_neighbors.run_state import NeighborKind
from zombies_aint_my_neighbors.sprite_kit import Part, PartKind, SpriteKit
from zombies_aint_my_neighbors.tv import Tv
from zombies_aint_my_neighbors.zap import Zap
from zombies_aint_my_neighbors.zombie import Zombie

DEX = Part(kind=PartKind.KID, variant='dex')
TV = Part(kind=PartKind.TV)
ZOMBIE = Part(kind=PartKind.ZOMBIE)
ZAP = Part(kind=PartKind.ZAP)
DOOR = Part(kind=PartKind.DOOR)
PIZZA_TEEN = Part(kind=PartKind.NEIGHBOR, variant=NeighborKind.PIZZA_TEEN)


def test_building_toward_needs_builds_one_sprite_a_call_until_they_are_met():
    """Each call builds the next part still missing; once all are ready, a call builds nothing."""
    kit = SpriteKit()
    needs = Counter({TV: 2, DEX: 1})

    built = [kit.build_one_toward(needs=needs) for _ in range(4)]

    assert built == [True, True, True, False]
    assert kit.ready(TV) == 2
    assert kit.ready(DEX) == 1
    assert kit.is_ready_for(needs=needs)


def test_building_ahead_draws_no_random_number():
    """A stage draws its random numbers as it is built (scene_start.py rule 4); the kit, none."""
    reset_streams(seed=7)
    random_stream('zombies_aint_my_neighbors.tv-spawns')
    before = capture_stream_states()
    kit = SpriteKit()
    needs = Counter({TV: 4, ZOMBIE: 1, ZAP: 1, DOOR: 1, DEX: 1, PIZZA_TEEN: 1})

    while kit.build_one_toward(needs=needs):
        pass

    assert capture_stream_states() == before


def test_waiting_sprites_are_in_the_kits_own_group_only():
    """Built sprites wait in the kit's storage group (the removed-sprites guard allows that)."""
    kit = SpriteKit()
    kit.build_one_toward(needs=Counter({DEX: 1}))

    for sprite in kit.storage.sprites():
        assert sprite.groups() == [kit.storage]


def test_taking_a_ready_part_loads_no_sprite_file(mocker):
    """A part built ahead is handed over as it is."""
    kit = SpriteKit()
    kit.build_one_toward(needs=Counter({ZOMBIE: 1}))
    loads = mocker.spy(AnimatedSprite, '__init__')

    zombie = kit.take_zombie(groups=pygame.sprite.LayeredDirty())

    assert loads.call_count == 0
    assert isinstance(zombie, Zombie)
    assert kit.ready(ZOMBIE) == 0


def test_taking_a_part_not_ready_builds_it_at_once(mocker):
    """The card skipped early, or a player joining mid-stage: the part is built on the spot."""
    kit = SpriteKit()
    loads = mocker.spy(AnimatedSprite, '__init__')

    tv = kit.take_tv(groups=pygame.sprite.LayeredDirty())

    assert isinstance(tv, Tv)
    assert loads.call_count > 0


def test_taking_a_kid_moves_it_and_its_props_into_the_group_in_creation_order():
    """A kid's remote, laser pointer, dot and beam come with it, in the order they were made."""
    kit = SpriteKit()
    kit.build_one_toward(needs=Counter({DEX: 1}))
    group = pygame.sprite.LayeredDirty()

    kid = kit.take_kid(look_name='dex', groups=group)

    assert isinstance(kid, Kid)
    # The order Kid.__init__ makes them in, as a kid built straight into the group has
    assert group.sprites() == [kid, kid.remote, kid.laser_pointer, kid.dot, kid.beam]
    assert kit.storage.sprites() == []
    assert all(sprite.groups() == [group] for sprite in group.sprites())


def test_taking_a_neighbor_brings_its_effects():
    """A neighbor's rescue and loss effects come with it."""
    kit = SpriteKit()
    group = pygame.sprite.LayeredDirty()

    neighbor = kit.take_neighbor(kind=NeighborKind.LAWN_CHAIR_READER, groups=group)

    assert isinstance(neighbor, Neighbor)
    assert neighbor.kind == NeighborKind.LAWN_CHAIR_READER
    assert sum(isinstance(sprite, NeighborEffect) for sprite in group.sprites()) == 2


def test_each_part_is_handed_over_once():
    """Taking two zaps after building one gives two different zaps: nothing is handed out twice."""
    kit = SpriteKit()
    kit.build_one_toward(needs=Counter({ZAP: 1}))

    first = kit.take_zap(groups=pygame.sprite.LayeredDirty())
    second = kit.take_zap(groups=pygame.sprite.LayeredDirty())

    assert isinstance(first, Zap)
    assert first is not second


def test_zombies_and_zaps_wait_put_away():
    """Pool sprites are handed over hidden, as a pool keeps them."""
    kit = SpriteKit()
    group = pygame.sprite.LayeredDirty()

    zombie = kit.take_zombie(groups=group)
    zap = kit.take_zap(groups=group)

    assert zombie.hidden
    assert zap.hidden


def test_kids_and_monsters_share_the_kits_mirror_cache():
    """Mirrored frames are made once for every stage the kit serves."""
    kit = SpriteKit()
    group = pygame.sprite.LayeredDirty()

    assert kit.take_kid(look_name='dex', groups=group).mirror_cache is kit.mirror_cache
    assert kit.take_zombie(groups=group).mirror_cache is kit.mirror_cache


def test_an_unknown_kid_is_refused():
    """A look with no sprite file is a bug to report, not a sprite to guess."""
    with pytest.raises(ValueError, match='nobody'):
        SpriteKit().take_kid(look_name='nobody', groups=pygame.sprite.LayeredDirty())


def test_a_part_of_the_wrong_type_is_a_builder_bug():
    """The kit's type check names both types rather than handing over the wrong sprite."""
    with pytest.raises(TypeError, match='Expected a Kid, got Zap'):
        sprite_kit._as(Kid, SpriteKit().take_zap(groups=pygame.sprite.LayeredDirty()))
