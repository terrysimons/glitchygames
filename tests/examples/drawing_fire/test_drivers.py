"""Tests for Drawing Fire's computer driver."""

from __future__ import annotations

import dataclasses
import math
import random

from glitchygames.examples.drawing_fire.battle import (
    MUZZLE_DISTANCE,
    PISTOL_COOLDOWN,
    PISTOL_RANGE,
    SAND_PER_HIT,
    SANDBAG_HEIGHT,
    SANDBAG_WIDTH,
    SOLDIER_CHEST_HEIGHT,
    Battle,
    Intent,
    Sandbag,
    Side,
)
from glitchygames.examples.drawing_fire.drivers import (
    ADVANCE_RANGE_FRACTION,
    AIM_ERROR_RADIANS,
    REACTION_SECONDS_RANGE,
    SANDBAG_COVER_DISTANCE,
    SANDBAG_SHOT_DISTANCE,
    SOLDIER_SPACING,
    STAND_OFF_FRACTION_RANGE,
    TARGET_SWITCH_MARGIN,
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
# Two hits of sand taken off a bag: it is lower than a soldier's chest and no longer blocks a walk
LOW_SAND = 1.0 - 2 * SAND_PER_HIT
# Two enemies this far apart (px) swap places as the nearest, within the target switch margin
NEAR_TIE_PIXELS = 7.5
HILL_LEFT = 300
HILL_RIGHT = 500
HILL_HEIGHT = 120.0
# Where a soldier stands to shoot a sandbag that blocks his way: between his muzzle's reach and
# the shooting distance, from the bag's near edge (px)
SHOOTING_SPOT_DISTANCE = (MUZZLE_DISTANCE + SANDBAG_SHOT_DISTANCE) / 2
# Ten seconds is long enough to shoot a blocking bag down (stepped STEPS_PER_SECOND a second)
BAG_SHOOTING_SECONDS = 10


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
    battle.sandbags[0].sand = LOW_SAND
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


def hill_battle(*, sandbag_x: float | None = None) -> Battle:
    """Build a one-a-side battle with a tall hill between the soldiers (they cannot see over it)."""
    ground = tuple(
        FLAT_GROUND_Y - (HILL_HEIGHT if HILL_LEFT <= x <= HILL_RIGHT else 0.0)
        for x in range(FIELD_WIDTH)
    )
    terrain = Terrain(width=FIELD_WIDTH, height=FIELD_HEIGHT, ground=ground)
    battle = Battle(
        terrain=terrain,
        soldiers_per_side=1,
        sandbag_xs=() if sandbag_x is None else (sandbag_x,),
    )
    battle.soldiers[0].x = 200.0
    battle.soldiers[1].x = 600.0
    for soldier in battle.soldiers:
        soldier.y = FLAT_GROUND_Y
    battle.seconds = AFTER_REACTION_SECONDS
    return battle


def test_a_walking_block_is_what_covers_a_soldier():
    """The driver's 'tall enough to cover' is the battle's walking-block rule: one number."""
    for hits in range(int(1 / SAND_PER_HIT) + 1):
        bag = Sandbag(x=0.0, width=SANDBAG_WIDTH, sand=1.0 - hits * SAND_PER_HIT)
        assert bag.blocks_walking == (bag.height > SOLDIER_CHEST_HEIGHT)
    assert Sandbag(x=0.0, width=SANDBAG_WIDTH, sand=1.0).height == SANDBAG_HEIGHT


def test_with_the_enemy_behind_a_hill_the_computer_walks_on_and_does_not_fire():
    """No clear line means no standing and no shooting, even within range."""
    battle = hill_battle()
    soldier = battle.soldiers[0]
    assert battle.soldiers[1].x - soldier.x <= PISTOL_RANGE
    intent = computer_intent(
        soldier=soldier, battle=battle, random=random.Random(1), mind=ComputerSoldier()
    )
    assert intent.move == 1.0
    assert not intent.fire


def test_stopped_at_a_sandbag_with_the_enemy_hidden_he_shoots_the_sandbags_middle():
    """He aims at the middle of the blocking bag (not level) and fires when ready."""
    bag_x = 240.0
    battle = hill_battle(sandbag_x=bag_x)
    soldier = battle.soldiers[0]
    soldier.x = bag_x - SANDBAG_WIDTH / 2 - SHOOTING_SPOT_DISTANCE
    bag = battle.sandbags[0]
    chest_x, chest_y = soldier.chest
    middle_y = FLAT_GROUND_Y - bag.height / 2
    expected_angle = math.atan2(chest_y - middle_y, bag_x - chest_x)
    held_error = 0.05
    mind = ComputerSoldier(target_id=1, aim_error=held_error)
    intent = computer_intent(soldier=soldier, battle=battle, random=random.Random(1), mind=mind)
    assert intent.move == 0.0
    # A shot at a sandbag follows the same rule as any shot: the held error, then a fresh one
    assert intent.aim_angle == expected_angle + held_error
    assert mind.aim_error != held_error
    assert intent.fire
    soldier.cooldown = PISTOL_COOLDOWN
    assert not computer_intent(
        soldier=soldier, battle=battle, random=random.Random(1), mind=mind
    ).fire


def test_too_near_a_blocking_sandbag_to_hit_it_he_steps_back_holding_fire():
    """Within his muzzle's reach his shots never hit the bag (his own cover), so he backs off."""
    bag_x = 240.0
    battle = hill_battle(sandbag_x=bag_x)
    soldier = battle.soldiers[0]
    soldier.x = bag_x - SANDBAG_WIDTH / 2 - SANDBAG_COVER_DISTANCE / 2
    intent = computer_intent(
        soldier=soldier, battle=battle, random=random.Random(1), mind=ComputerSoldier(target_id=1)
    )
    assert intent.move == -1.0
    assert not intent.fire


def test_the_computers_shots_wear_down_a_sandbag_that_blocks_his_way():
    """Walking up to a blocking bag with the enemy behind a hill, he shoots it down and walks on.

    His own cover is never hit by his shots (battle.Bullet.ignored_sandbags), so this checks
    that a bag ahead of him, the one he means to shoot, still is.
    """
    bag_x = 240.0
    battle = hill_battle(sandbag_x=bag_x)
    soldier = battle.soldiers[0]
    bag = battle.sandbags[0]
    mind = ComputerSoldier(target_id=1)
    stream = random.Random(1)
    for _ in range(BAG_SHOOTING_SECONDS * STEPS_PER_SECOND):
        intent = computer_intent(soldier=soldier, battle=battle, random=stream, mind=mind)
        battle.step(dt=1 / STEPS_PER_SECOND, intents={soldier.soldier_id: intent})
    assert not bag.blocks_walking
    assert soldier.x > bag_x


def test_once_the_sandbag_is_low_enough_to_walk_over_he_walks_on():
    """A bag below the walking-block height is no longer shot at; he walks on."""
    bag_x = 240.0
    battle = hill_battle(sandbag_x=bag_x)
    soldier = battle.soldiers[0]
    soldier.x = bag_x - SANDBAG_WIDTH / 2 - SANDBAG_COVER_DISTANCE / 2
    battle.sandbags[0].sand = LOW_SAND
    intent = computer_intent(
        soldier=soldier, battle=battle, random=random.Random(1), mind=ComputerSoldier()
    )
    assert intent.move == 1.0
    assert not intent.fire


def test_blocked_by_a_sandbag_with_the_enemy_in_sight_but_out_of_range_he_shoots_it():
    """Pushing into a bag forever is no use: he shoots it when the enemy is too far to shoot."""
    battle = small_battle(sandbag_xs=(240.0,))
    soldier = battle.soldiers[0]
    soldier.x = 240.0 - SANDBAG_WIDTH / 2 - SHOOTING_SPOT_DISTANCE
    battle.soldiers[1].x = soldier.x + PISTOL_RANGE + 100.0
    battle.seconds = AFTER_REACTION_SECONDS
    intent = computer_intent(
        soldier=soldier, battle=battle, random=random.Random(1), mind=ComputerSoldier(target_id=1)
    )
    assert intent.move == 0.0
    assert intent.fire


def test_nearly_equidistant_enemies_do_not_keep_changing_his_target():
    """Two enemies trading places as the nearest cannot stop him from firing."""
    assert 0.0 < NEAR_TIE_PIXELS < TARGET_SWITCH_MARGIN
    battle = Battle(terrain=small_battle().terrain, soldiers_per_side=2, sandbag_xs=())
    shooter = battle.soldiers[0]
    first, second = battle.soldiers[2], battle.soldiers[3]
    first.x = shooter.x + 200.0
    second.x = first.x + NEAR_TIE_PIXELS
    mind = ComputerSoldier()
    stream = random.Random(5)
    fired = False
    for frame in range(120):
        battle.seconds = frame / 60
        # They trade places as the nearest each frame
        near, far = (first, second) if frame % 2 else (second, first)
        near.x, far.x = shooter.x + 200.0, shooter.x + 200.0 + NEAR_TIE_PIXELS
        intent = computer_intent(soldier=shooter, battle=battle, random=stream, mind=mind)
        fired = fired or intent.fire
    assert fired


def test_he_switches_to_an_enemy_that_is_clearly_nearer():
    """Past the margin, or when the target dies, he retargets."""
    battle = Battle(terrain=small_battle().terrain, soldiers_per_side=2, sandbag_xs=())
    shooter = battle.soldiers[0]
    first, second = battle.soldiers[2], battle.soldiers[3]
    first.x, second.x = shooter.x + 200.0, shooter.x + 250.0
    mind = ComputerSoldier()
    stream = random.Random(5)
    computer_intent(soldier=shooter, battle=battle, random=stream, mind=mind)
    assert mind.target_id == first.soldier_id
    second.x = shooter.x + 200.0 - TARGET_SWITCH_MARGIN * 2
    computer_intent(soldier=shooter, battle=battle, random=stream, mind=mind)
    assert mind.target_id == second.soldier_id
    second.health = 0
    computer_intent(soldier=shooter, battle=battle, random=stream, mind=mind)
    assert mind.target_id == first.soldier_id


def test_each_soldier_draws_his_stand_off_once_from_his_own_stream():
    """Stand-offs lie in the range, differ between soldiers, and replay with the seed."""
    reset_streams(seed=TEST_SEED)
    _, minds, _ = muster_battle(
        battle_number=1, width=FIELD_WIDTH, height=FIELD_HEIGHT, soldiers_per_side=4
    )
    fractions = [mind.stand_off_fraction for mind in minds.values()]
    assert all(
        STAND_OFF_FRACTION_RANGE[0] <= fraction <= STAND_OFF_FRACTION_RANGE[1]
        for fraction in fractions
    )
    assert len(set(fractions)) > 1
    reset_streams(seed=TEST_SEED)
    _, again, _ = muster_battle(
        battle_number=1, width=FIELD_WIDTH, height=FIELD_HEIGHT, soldiers_per_side=4
    )
    assert [mind.stand_off_fraction for mind in again.values()] == fractions


def test_a_soldier_stands_at_his_own_stand_off():
    """With a shorter stand-off he keeps walking where another would already stand."""
    battle = small_battle()
    soldier = battle.soldiers[0]
    distance = PISTOL_RANGE * sum(STAND_OFF_FRACTION_RANGE) / 2
    place_enemy(battle, distance=distance)
    near = ComputerSoldier(stand_off_fraction=STAND_OFF_FRACTION_RANGE[1])
    far = ComputerSoldier(stand_off_fraction=STAND_OFF_FRACTION_RANGE[0])
    assert (
        computer_intent(soldier=soldier, battle=battle, random=random.Random(1), mind=near).move
        == 0.0
    )
    assert (
        computer_intent(soldier=soldier, battle=battle, random=random.Random(1), mind=far).move
        == 1.0
    )


def test_the_aim_is_held_steady_between_shots():
    """The aim error is drawn once per shot, so the aim does not shake from frame to frame."""
    battle = small_battle()
    place_enemy(battle, distance=200.0)
    soldier = battle.soldiers[0]
    stream = random.Random(8)
    mind = ComputerSoldier()
    first = computer_intent(soldier=soldier, battle=battle, random=stream, mind=mind)
    # He is still reacting, so these frames fire nothing
    assert not first.fire
    state = stream.getstate()
    for _ in range(10):
        again = computer_intent(soldier=soldier, battle=battle, random=stream, mind=mind)
        assert again.aim_angle == first.aim_angle
    assert stream.getstate() == state


def test_the_aim_error_is_redrawn_after_each_shot_and_for_a_new_target():
    """A fresh error follows every shot, and a new target draws one too."""
    battle = small_battle()
    place_enemy(battle, distance=200.0)
    soldier = battle.soldiers[0]
    stream = random.Random(9)
    mind = ComputerSoldier()
    computer_intent(soldier=soldier, battle=battle, random=stream, mind=mind)
    battle.seconds = AFTER_REACTION_SECONDS
    held_error = mind.aim_error
    shot = computer_intent(soldier=soldier, battle=battle, random=stream, mind=mind)
    assert shot.fire
    # The shot used the held error; the next shot has a new one
    assert mind.aim_error != held_error
    mind.target_id = None
    previous_error = mind.aim_error
    computer_intent(soldier=soldier, battle=battle, random=stream, mind=mind)
    assert mind.aim_error != previous_error


def test_the_held_aim_is_deterministic():
    """The same stream gives the same aim errors."""
    battle = small_battle()
    place_enemy(battle, distance=200.0)
    aims = []
    for _ in range(2):
        mind = ComputerSoldier()
        stream = random.Random(10)
        aims.append(
            computer_intent(
                soldier=battle.soldiers[0], battle=battle, random=stream, mind=mind
            ).aim_angle
        )
    assert aims[0] == aims[1]


def two_a_side_battle(*, sandbag_xs: tuple[float, ...] = ()) -> Battle:
    """Build a two-a-side battle on flat ground (Platoon ids 0 and 1, Brigade ids 2 and 3)."""
    terrain = Terrain(width=FIELD_WIDTH, height=FIELD_HEIGHT, ground=(FLAT_GROUND_Y,) * FIELD_WIDTH)
    battle = Battle(terrain=terrain, soldiers_per_side=2, sandbag_xs=sandbag_xs)
    for soldier in battle.soldiers:
        soldier.y = FLAT_GROUND_Y
    battle.soldiers[2].x = 700.0
    battle.soldiers[3].x = 720.0
    return battle


def test_a_soldier_crowded_by_a_friend_of_higher_priority_walks_on():
    """Standing on a friend's spot, the Platoon's rear soldier walks on and its front one holds."""
    battle = two_a_side_battle()
    holder, mover = battle.soldiers[1], battle.soldiers[0]
    holder.x = 500.0
    # In range and within his stand-off, so he would stand
    battle.soldiers[2].x = holder.x + PISTOL_RANGE * STAND_OFF_FRACTION_RANGE[0] - 20.0
    battle.soldiers[3].x = battle.soldiers[2].x + 10.0
    mover.x = holder.x + SOLDIER_SPACING - 1.0
    battle.seconds = AFTER_REACTION_SECONDS

    def move_of(soldier):
        return computer_intent(
            soldier=soldier,
            battle=battle,
            random=random.Random(1),
            mind=ComputerSoldier(stand_off_fraction=STAND_OFF_FRACTION_RANGE[1]),
        ).move

    assert move_of(holder) == 0.0
    assert move_of(mover) == 1.0
    mover.x = holder.x + SOLDIER_SPACING + 1.0
    assert move_of(mover) == 0.0


def test_the_brigades_front_soldier_holds_its_spot_as_the_platoons_does():
    """Neither army's front soldier is the one to give way: the Brigade's lowest id holds."""
    battle = two_a_side_battle()
    holder, mover = battle.soldiers[2], battle.soldiers[3]
    holder.x = 500.0
    mover.x = holder.x + SOLDIER_SPACING - 1.0
    battle.soldiers[0].x = holder.x - PISTOL_RANGE * STAND_OFF_FRACTION_RANGE[0] + 20.0
    battle.soldiers[1].x = battle.soldiers[0].x - 10.0
    battle.seconds = AFTER_REACTION_SECONDS

    def move_of(soldier):
        return computer_intent(
            soldier=soldier,
            battle=battle,
            random=random.Random(1),
            mind=ComputerSoldier(stand_off_fraction=STAND_OFF_FRACTION_RANGE[1]),
        ).move

    assert move_of(holder) == 0.0
    assert move_of(mover) == -1.0


def test_soldiers_queue_a_spacing_apart_behind_a_sandbag_that_blocks_them():
    """A friend ahead within a spacing holds him in place, a spacing farther back he walks on."""
    bag_x = 300.0
    battle = two_a_side_battle(sandbag_xs=(bag_x,))
    battle.soldiers[2].x = 790.0
    battle.soldiers[3].x = 799.0
    head, follower = battle.soldiers[0], battle.soldiers[1]
    near_edge = bag_x - SANDBAG_WIDTH / 2
    head.x = near_edge - SHOOTING_SPOT_DISTANCE
    follower.x = head.x - SOLDIER_SPACING + 1.0
    # The enemy is far out of range, so cover is no place to stand yet: only the queue holds him
    battle.seconds = AFTER_REACTION_SECONDS

    def move_of(soldier):
        return computer_intent(
            soldier=soldier, battle=battle, random=random.Random(1), mind=ComputerSoldier()
        ).move

    assert move_of(follower) == 0.0
    follower.x = head.x - SOLDIER_SPACING - 1.0
    assert move_of(follower) == 1.0
    # The head of the queue stands at the bag (shooting it down), as nobody is ahead of him
    assert move_of(head) == 0.0


# A player who walks through the enemy line, and how long he walks (s, at 60 steps a second)
PLAYER_WALK_SECONDS = 20.0
STEPS_PER_SECOND = 60
# Health no pistol can take in the walk: the player must reach the far side
UNTOUCHABLE_HEALTH = 10_000


def test_no_computer_friend_follows_a_player_through_the_enemy_line():
    """A player walks his soldier through the Brigade: his friends never pass the enemy's front.

    The Platoon's front soldier has the highest priority, so friends crowded by him give way by
    walking on. Before the fix their way off was kept until they were clear, and a player
    walking on at the same speed never let them clear, so they followed him to the field's edge.
    No one fires (and the sandbags are taken away), so the enemy's line stays where it stands.
    """
    reset_streams(seed=TEST_SEED)
    battle, minds, streams = muster_battle(
        battle_number=1, width=FIELD_WIDTH, height=FIELD_HEIGHT, soldiers_per_side=8
    )
    # Standing sandbags block walking, and no one shoots them down here
    battle.sandbags.clear()
    # The Platoon's front soldier (the highest priority), started behind his friends, so he
    # walks through them as the golden replay's player did
    player = max(battle.living(Side.PLATOON), key=lambda soldier: soldier.x)
    player.x = min(friend.x for friend in battle.living(Side.PLATOON))
    player.health = UNTOUCHABLE_HEALTH
    farthest_past_front = -math.inf
    for _ in range(round(PLAYER_WALK_SECONDS * STEPS_PER_SECOND)):
        intents = {
            soldier_id: dataclasses.replace(intent, fire=False)
            for soldier_id, intent in computer_intents(
                battle=battle, minds=minds, streams=streams
            ).items()
        }
        intents[player.soldier_id] = Intent(move=1.0, aim_angle=0.0, fire=False)
        battle.step(dt=1 / STEPS_PER_SECOND, intents=intents)
        enemy_front_x = min(enemy.x for enemy in battle.living(Side.BRIGADE))
        farthest_past_front = max(
            farthest_past_front,
            *(
                friend.x - enemy_front_x
                for friend in battle.living(Side.PLATOON)
                if friend is not player
            ),
        )
    assert player.x > max(enemy.x for enemy in battle.living(Side.BRIGADE))
    assert farthest_past_front <= 0.0
