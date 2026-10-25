"""Tests for Drawing Fire's computer driver."""

from __future__ import annotations

import math
import random

from glitchygames.examples.drawing_fire.battle import (
    PISTOL_COOLDOWN,
    PISTOL_RANGE,
    SANDBAG_HEIGHT,
    SOLDIER_CHEST_HEIGHT,
    Battle,
    Side,
)
from glitchygames.examples.drawing_fire.drivers import (
    ADVANCE_RANGE_FRACTION,
    AIM_ERROR_RADIANS,
    REACTION_SECONDS_RANGE,
    SANDBAG_COVER_DISTANCE,
    ComputerSoldier,
    computer_intent,
    computer_intents,
    muster_battle,
    soldier_stream_name,
)
from glitchygames.examples.drawing_fire.terrain import Terrain
from glitchygames.randomness import random_stream, reset_streams

FIELD_WIDTH = 800
FIELD_HEIGHT = 480
FLAT_GROUND_Y = 400.0
TEST_SEED = 20261025
AFTER_REACTION_SECONDS = REACTION_SECONDS_RANGE[1] + 0.01
# Many aim samples, to check the error's spread
AIM_SAMPLES = 400


def small_battle(*, sandbag_xs: tuple[float, ...] = ()) -> Battle:
    """Build a one-a-side battle on flat ground."""
    terrain = Terrain(width=FIELD_WIDTH, height=FIELD_HEIGHT, ground=(FLAT_GROUND_Y,) * FIELD_WIDTH)
    return Battle(terrain=terrain, soldiers_per_side=1, sandbag_xs=sandbag_xs)


def place_enemy(battle: Battle, *, distance: float) -> None:
    """Put the Brigade soldier this far from the Platoon soldier, on the same ground."""
    battle.soldiers[1].x = battle.soldiers[0].x + distance


def test_the_stream_name_holds_the_battle_and_the_soldier():
    """Each soldier in each battle has a stream of his own."""
    assert soldier_stream_name(battle_number=3, soldier_id=5) == 'drawing_fire.soldier.3.5'


def test_a_soldier_draws_only_from_his_own_stream():
    """Deciding for one soldier never touches another soldier's stream."""
    battle = small_battle()
    mine, other = random.Random(1), random.Random(2)
    other_state = other.getstate()
    computer_intent(soldier=battle.soldiers[0], battle=battle, random=mine, mind=ComputerSoldier())
    assert other.getstate() == other_state


def test_the_computer_aims_at_the_nearest_enemy():
    """The aim is near the true bearing of the nearest enemy, not a farther one."""
    battle = Battle(terrain=small_battle().terrain, soldiers_per_side=2, sandbag_xs=())
    shooter = battle.soldiers[0]
    near, far = battle.soldiers[2], battle.soldiers[3]
    near.x, far.x = shooter.x + 200.0, shooter.x + 300.0
    near.y = FLAT_GROUND_Y - 80.0  # on a rise, so the true bearing is above level
    intent = computer_intent(
        soldier=shooter, battle=battle, random=random.Random(4), mind=ComputerSoldier()
    )
    near_chest_x, near_chest_y = near.chest
    shooter_chest_x, shooter_chest_y = shooter.chest
    bearing = math.atan2(shooter_chest_y - near_chest_y, near_chest_x - shooter_chest_x)
    assert abs(intent.aim_angle - bearing) <= AIM_ERROR_RADIANS * 4


def test_the_aim_error_is_centred_on_the_bearing():
    """Over many samples the error averages near zero and is not all zero."""
    battle = small_battle()
    place_enemy(battle, distance=200.0)
    stream = random.Random(6)
    errors = [
        computer_intent(
            soldier=battle.soldiers[0], battle=battle, random=stream, mind=ComputerSoldier()
        ).aim_angle
        for _ in range(AIM_SAMPLES)
    ]
    mean = sum(errors) / AIM_SAMPLES
    assert abs(mean) < AIM_ERROR_RADIANS / 4
    assert max(errors) > 0.0 > min(errors)


def test_the_computer_advances_until_in_range():
    """He walks toward the enemy while far, and stands once within the advance range."""
    battle = small_battle()
    soldier = battle.soldiers[0]
    place_enemy(battle, distance=PISTOL_RANGE * ADVANCE_RANGE_FRACTION + 50.0)
    mind = ComputerSoldier()
    assert (
        computer_intent(soldier=soldier, battle=battle, random=random.Random(1), mind=mind).move
        == 1.0
    )
    place_enemy(battle, distance=PISTOL_RANGE * ADVANCE_RANGE_FRACTION - 1.0)
    assert (
        computer_intent(soldier=soldier, battle=battle, random=random.Random(1), mind=mind).move
        == 0.0
    )


def test_the_brigade_advances_to_the_left():
    """A soldier on the right walks left toward the enemy."""
    battle = small_battle()
    place_enemy(battle, distance=PISTOL_RANGE * 2)
    intent = computer_intent(
        soldier=battle.soldiers[1], battle=battle, random=random.Random(1), mind=ComputerSoldier()
    )
    assert intent.move == -1.0


def test_the_computer_with_no_enemy_stands_still():
    """Once the enemy is gone he does nothing."""
    battle = small_battle()
    battle.soldiers[1].health = 0
    soldier = battle.soldiers[0]
    intent = computer_intent(
        soldier=soldier, battle=battle, random=random.Random(1), mind=ComputerSoldier()
    )
    assert (intent.move, intent.fire, intent.aim_angle) == (0.0, False, soldier.aim_angle)


def test_the_computer_waits_out_the_reaction_delay_per_new_target():
    """He fires only after the delay drawn for his target, and again waits for a new one."""
    battle = small_battle()
    place_enemy(battle, distance=200.0)
    soldier = battle.soldiers[0]
    stream = random.Random(9)
    mind = ComputerSoldier()
    assert not computer_intent(soldier=soldier, battle=battle, random=stream, mind=mind).fire
    battle.seconds = AFTER_REACTION_SECONDS
    assert computer_intent(soldier=soldier, battle=battle, random=stream, mind=mind).fire
    # The delay is drawn once per target: asking again for the same target keeps it
    ready_at = mind.fire_ready_at
    computer_intent(soldier=soldier, battle=battle, random=stream, mind=mind)
    assert mind.fire_ready_at == ready_at
    assert mind.target_id == battle.soldiers[1].soldier_id


def test_the_computer_does_not_fire_on_cooldown_or_out_of_range():
    """The pistol must be ready and the enemy within its range."""
    battle = small_battle()
    soldier = battle.soldiers[0]
    battle.seconds = AFTER_REACTION_SECONDS
    place_enemy(battle, distance=200.0)
    mind = ComputerSoldier()
    soldier.cooldown = PISTOL_COOLDOWN
    assert not computer_intent(
        soldier=soldier, battle=battle, random=random.Random(1), mind=mind
    ).fire
    soldier.cooldown = 0.0
    place_enemy(battle, distance=PISTOL_RANGE + 50.0)
    assert not computer_intent(
        soldier=soldier, battle=battle, random=random.Random(1), mind=mind
    ).fire


def test_the_computer_shelters_behind_a_standing_sandbag_when_the_enemy_is_in_range():
    """He walks to a covering sandbag on his way and stops at its near edge."""
    battle = small_battle()
    soldier = battle.soldiers[0]
    place_enemy(battle, distance=PISTOL_RANGE - 10.0)
    sandbag_x = soldier.x + 60.0
    battle.sandbags = small_battle(sandbag_xs=(sandbag_x,)).sandbags
    mind = ComputerSoldier()
    assert (
        computer_intent(soldier=soldier, battle=battle, random=random.Random(1), mind=mind).move
        == 1.0
    )
    soldier.x = sandbag_x - battle.sandbags[0].width / 2 - SANDBAG_COVER_DISTANCE / 2
    assert (
        computer_intent(soldier=soldier, battle=battle, random=random.Random(1), mind=mind).move
        == 0.0
    )


def test_the_computer_ignores_a_sandbag_that_no_longer_covers_him():
    """A worn-down bag no taller than his chest is not worth stopping for."""
    battle = small_battle()
    soldier = battle.soldiers[0]
    place_enemy(battle, distance=PISTOL_RANGE - 10.0)
    battle.sandbags = small_battle(sandbag_xs=(soldier.x + 60.0,)).sandbags
    battle.sandbags[0].sand = SOLDIER_CHEST_HEIGHT / SANDBAG_HEIGHT
    soldier.x = battle.sandbags[0].x - battle.sandbags[0].width / 2
    assert (
        computer_intent(
            soldier=soldier, battle=battle, random=random.Random(1), mind=ComputerSoldier()
        ).move
        == 1.0
    )


def test_the_computer_does_not_stop_for_a_sandbag_behind_him_or_far_ahead():
    """Only a sandbag ahead and near counts."""
    battle = small_battle()
    soldier = battle.soldiers[0]
    place_enemy(battle, distance=PISTOL_RANGE - 10.0)
    soldier.x = 300.0
    battle.soldiers[1].x = soldier.x + PISTOL_RANGE - 10.0
    behind = small_battle(sandbag_xs=(soldier.x - 100.0,)).sandbags
    battle.sandbags = behind
    mind = ComputerSoldier()
    assert (
        computer_intent(soldier=soldier, battle=battle, random=random.Random(1), mind=mind).move
        == 1.0
    )
    battle.sandbags = small_battle(sandbag_xs=(soldier.x + 400.0,)).sandbags
    assert (
        computer_intent(soldier=soldier, battle=battle, random=random.Random(1), mind=mind).move
        == 1.0
    )


def test_the_computer_keeps_walking_past_a_sandbag_while_the_enemy_is_out_of_range():
    """Cover is for fighting, so a far enemy does not stop him at a sandbag."""
    battle = small_battle()
    soldier = battle.soldiers[0]
    place_enemy(battle, distance=PISTOL_RANGE + 100.0)
    battle.sandbags = small_battle(sandbag_xs=(soldier.x + 30.0,)).sandbags
    soldier.x = battle.sandbags[0].x - battle.sandbags[0].width / 2
    assert (
        computer_intent(
            soldier=soldier, battle=battle, random=random.Random(1), mind=ComputerSoldier()
        ).move
        == 1.0
    )


def test_muster_battle_gives_every_soldier_his_own_seeded_stream():
    """The same seed musters the same battle, and each soldier has a distinct stream."""
    reset_streams(seed=TEST_SEED)
    battle, minds, streams = muster_battle(
        battle_number=1, width=FIELD_WIDTH, height=FIELD_HEIGHT, soldiers_per_side=3
    )
    assert set(minds) == set(streams) == {soldier.soldier_id for soldier in battle.soldiers}
    assert streams[0] is random_stream(soldier_stream_name(battle_number=1, soldier_id=0))
    assert streams[0] is not streams[1]
    reset_streams(seed=TEST_SEED)
    again, _, _ = muster_battle(
        battle_number=1, width=FIELD_WIDTH, height=FIELD_HEIGHT, soldiers_per_side=3
    )
    assert again.terrain == battle.terrain
    assert [bag.x for bag in again.sandbags] == [bag.x for bag in battle.sandbags]


def test_computer_intents_cover_only_the_living():
    """The dead are given no intent."""
    reset_streams(seed=TEST_SEED)
    battle, minds, streams = muster_battle(
        battle_number=1, width=FIELD_WIDTH, height=FIELD_HEIGHT, soldiers_per_side=2
    )
    battle.soldiers[0].health = 0
    intents = computer_intents(battle=battle, minds=minds, streams=streams)
    assert set(intents) == {1, 2, 3}
    assert battle.soldiers[1].side is Side.PLATOON
