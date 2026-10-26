"""Tests for Drawing Fire's battle model: soldiers, pistols, bullets, sandbags, the winner."""

from __future__ import annotations

import math
import random

import pytest

from drawing_fire.battle import (
    ARMY_NAMES,
    MUZZLE_DISTANCE,
    PISTOL_COOLDOWN,
    PISTOL_DAMAGE,
    PISTOL_RANGE,
    SAND_PER_HIT,
    SANDBAG_HEIGHT,
    SANDBAG_MAX_GROUND_VARIATION,
    SANDBAG_WIDTH,
    SOLDIER_HEALTH,
    WALK_SPEED,
    Battle,
    BattleEvent,
    Intent,
    Sandbag,
    SandbagFlattened,
    Side,
    Soldier,
    SoldierKilled,
    sandbag_positions,
)
from drawing_fire.terrain import Terrain, build_terrain

FIELD_WIDTH = 800
FIELD_HEIGHT = 480
FLAT_GROUND_Y = 400.0
TIME_STEP = 0.01
# Time for a bullet to cross a duel's distance, after the shot that fires it
BULLET_FLIGHT_SLACK_SECONDS = 0.5


def flat_terrain() -> Terrain:
    """Build perfectly flat ground, for exact geometry."""
    return Terrain(
        width=FIELD_WIDTH,
        height=FIELD_HEIGHT,
        ground=(FLAT_GROUND_Y,) * FIELD_WIDTH,
    )


def flat_battle(
    *,
    soldiers_per_side: int = 4,
    sandbag_xs: tuple[float, ...] = (),
) -> Battle:
    """Build a battle on flat ground."""
    return Battle(
        terrain=flat_terrain(),
        soldiers_per_side=soldiers_per_side,
        sandbag_xs=sandbag_xs,
    )


def run(battle: Battle, *, seconds: float, intents: dict[int, Intent]) -> list[BattleEvent]:
    """Step the battle for some seconds with the same intents, collecting the events."""
    events: list[BattleEvent] = []
    for _ in range(round(seconds / TIME_STEP)):
        events.extend(battle.step(dt=TIME_STEP, intents=intents))
    return events


def duel(
    *,
    distance: float,
    terrain: Terrain | None = None,
    sandbag_xs: tuple[float, ...] = (),
) -> tuple[Battle, Soldier, Soldier]:
    """Set one Platoon shooter facing one Brigade target at the same height."""
    battle = Battle(
        terrain=terrain if terrain is not None else flat_terrain(),
        soldiers_per_side=1,
        sandbag_xs=sandbag_xs,
    )
    shooter = battle.living(Side.PLATOON)[0]
    target = battle.living(Side.BRIGADE)[0]
    shooter.x = 100.0
    shooter.y = battle.terrain.ground_y(shooter.x)
    target.x = shooter.x + distance
    target.y = battle.terrain.ground_y(target.x)
    return battle, shooter, target


def test_sides_know_their_opponent_and_their_army_names():
    """Each side's opponent is the other side, and the armies have their names."""
    assert Side.PLATOON.opponent is Side.BRIGADE
    assert Side.BRIGADE.opponent is Side.PLATOON
    assert ARMY_NAMES == {Side.PLATOON: 'Pencil Platoon', Side.BRIGADE: 'Graphite Brigade'}


def test_armies_spawn_on_their_own_sides():
    """Platoon stands in the left fifth and Brigade in the right fifth, facing each other."""
    battle = flat_battle(soldiers_per_side=4)
    assert [soldier.soldier_id for soldier in battle.soldiers] == list(range(8))
    assert all(s.x < battle.terrain.width / 5 for s in battle.living(Side.PLATOON))
    assert all(s.x > battle.terrain.width * 4 / 5 for s in battle.living(Side.BRIGADE))
    assert len({soldier.x for soldier in battle.soldiers}) == 8
    assert all(soldier.y == FLAT_GROUND_Y for soldier in battle.soldiers)
    assert all(soldier.health == SOLDIER_HEALTH for soldier in battle.soldiers)
    assert battle.soldier(0).aim_angle == 0.0
    assert battle.soldier(7).aim_angle == pytest.approx(math.pi)


def test_the_muzzle_is_out_along_the_aim_at_chest_height():
    """Aimed right the muzzle is ahead of the soldier; aimed up it is above the chest."""
    soldier = Soldier(
        soldier_id=0, side=Side.PLATOON, x=100.0, y=400.0, health=3, aim_angle=0.0, cooldown=0.0
    )
    muzzle_x, muzzle_y = soldier.muzzle
    assert muzzle_x > soldier.x
    assert soldier.y - 40.0 < muzzle_y < soldier.y
    soldier.aim_angle = math.pi / 2
    up_x, up_y = soldier.muzzle
    assert up_x == pytest.approx(soldier.x)
    assert up_y < muzzle_y


def test_a_shot_hits_the_enemy_it_is_aimed_at():
    """Facing soldiers at the same height, no sandbag: two shots land (at 0 and at the cooldown)."""
    battle, shooter, target = duel(distance=200)
    # The cooldown allows two shots: at 0 and at PISTOL_COOLDOWN; the second needs time to land
    run(
        battle,
        seconds=PISTOL_COOLDOWN + BULLET_FLIGHT_SLACK_SECONDS,
        intents={shooter.soldier_id: Intent(aim_angle=0.0, fire=True)},
    )
    assert target.health == SOLDIER_HEALTH - 2


def test_enough_hits_kill_and_report_it():
    """The last hit of SOLDIER_HEALTH kills, SoldierKilled is reported once, and the dead stop."""
    battle, shooter, target = duel(distance=200)
    events = run(
        battle,
        seconds=SOLDIER_HEALTH * PISTOL_COOLDOWN + BULLET_FLIGHT_SLACK_SECONDS,
        intents={shooter.soldier_id: Intent(fire=True)},
    )
    assert events == [SoldierKilled(target.soldier_id)]
    assert not target.alive
    assert target.health == 0
    assert battle.living(Side.BRIGADE) == []


def test_bullets_never_hit_their_own_side():
    """A friend standing in the line of fire is not hit, the enemy behind is."""
    battle = flat_battle(soldiers_per_side=2)
    shooter, friend = battle.living(Side.PLATOON)
    far_enemy = battle.living(Side.BRIGADE)[0]
    shooter.x, friend.x, far_enemy.x = 100.0, 150.0, 300.0
    for soldier in (shooter, friend, far_enemy):
        soldier.y = FLAT_GROUND_Y
    run(battle, seconds=0.5, intents={shooter.soldier_id: Intent(fire=True)})
    assert friend.health == SOLDIER_HEALTH
    assert far_enemy.health < SOLDIER_HEALTH


def test_a_shot_sandbag_loses_sand_and_flattens():
    """Four hits take a sandbag from 0.75 sand to flat, and SandbagFlattened is reported once."""
    battle, shooter, target = duel(distance=300, sandbag_xs=(250.0,))
    bag = battle.sandbags[0]
    assert bag.sand == 1.0
    assert bag.height == SANDBAG_HEIGHT
    sand_after_each_hit = []
    events: list[BattleEvent] = []
    # A level shot clears a bag once it is under chest height, so aim at the bag's foot
    muzzle_x, muzzle_y = shooter.muzzle
    aim_at_the_foot = -math.atan2(FLAT_GROUND_Y - 2.0 - muzzle_y, bag.x - muzzle_x)
    intents = {shooter.soldier_id: Intent(aim_angle=aim_at_the_foot, fire=True)}
    max_steps = round(10.0 / TIME_STEP)  # bounded, so a regression fails instead of hanging
    for _ in range(max_steps):
        events.extend(battle.step(dt=TIME_STEP, intents=intents))
        if not sand_after_each_hit or bag.sand != sand_after_each_hit[-1]:
            sand_after_each_hit.append(bag.sand)
        if bag.flattened:
            break
    assert sand_after_each_hit == [1.0, 0.75, 0.5, 0.25, 0.0]
    assert events == [SandbagFlattened(index=0)]
    assert bag.height == 0.0
    assert target.health == SOLDIER_HEALTH
    # Once flat, level shots go over it and land
    run(
        battle,
        seconds=PISTOL_COOLDOWN + BULLET_FLIGHT_SLACK_SECONDS,
        intents={shooter.soldier_id: Intent(fire=True)},
    )
    assert target.health < SOLDIER_HEALTH
    assert bag.sand == 0.0


def test_a_fresh_sandbag_covers_a_soldier_from_level_fire_for_two_hits():
    """Level chest-height fire is stopped by a fresh bag twice, then it reaches the soldier."""
    battle, shooter, target = duel(distance=300, sandbag_xs=(250.0,))
    bag = battle.sandbags[0]
    chest_height = shooter.y - shooter.muzzle[1]
    intents = {shooter.soldier_id: Intent(fire=True)}
    hits_covered = 0
    while bag.height > chest_height:
        sand_before = bag.sand
        shooter.cooldown = 0.0
        battle.step(dt=TIME_STEP, intents=intents)
        run(battle, seconds=1.0, intents={})  # let the bullet land
        assert bag.sand < sand_before
        assert target.health == SOLDIER_HEALTH
        hits_covered += 1
    assert hits_covered == 2
    shooter.cooldown = 0.0
    battle.step(dt=TIME_STEP, intents=intents)
    run(battle, seconds=1.0, intents={})
    assert target.health == SOLDIER_HEALTH - PISTOL_DAMAGE


def test_a_standing_sandbag_blocks_walking_and_a_flat_one_does_not():
    """A tall sandbag stops a soldier at its edge; a flattened one is walked over."""
    battle = flat_battle(soldiers_per_side=1, sandbag_xs=(200.0,))
    walker = battle.living(Side.PLATOON)[0]
    walker.x = 100.0
    run(battle, seconds=3.0, intents={walker.soldier_id: Intent(move=1.0)})
    assert walker.x == pytest.approx(200.0 - SANDBAG_WIDTH / 2)

    battle.sandbags[0].sand = 0.0
    run(battle, seconds=1.0, intents={walker.soldier_id: Intent(move=1.0)})
    assert walker.x > 200.0 + SANDBAG_WIDTH / 2 - WALK_SPEED * 0.1  # past the bag's far side


def test_a_standing_sandbag_blocks_walking_from_the_other_side():
    """The same sandbag stops a soldier walking left into its right edge."""
    battle = flat_battle(soldiers_per_side=1, sandbag_xs=(200.0,))
    walker = battle.living(Side.PLATOON)[0]
    walker.x = 300.0
    run(battle, seconds=3.0, intents={walker.soldier_id: Intent(move=-1.0)})
    assert walker.x == pytest.approx(200.0 + SANDBAG_WIDTH / 2)


def test_a_half_flattened_sandbag_no_longer_blocks_walking():
    """Under half a soldier tall, a sandbag is stepped over."""
    battle = flat_battle(soldiers_per_side=1, sandbag_xs=(200.0,))
    battle.sandbags[0].sand = 0.5
    walker = battle.living(Side.PLATOON)[0]
    walker.x = 100.0
    run(battle, seconds=3.0, intents={walker.soldier_id: Intent(move=1.0)})
    assert walker.x > 200.0 + SANDBAG_WIDTH / 2


def test_walking_is_clamped_to_walk_speed_and_stays_on_the_field():
    """Move beyond +-1 is clamped, and no one walks off either edge."""
    battle = flat_battle(soldiers_per_side=1)
    walker = battle.living(Side.PLATOON)[0]
    start = walker.x
    battle.step(dt=0.1, intents={walker.soldier_id: Intent(move=5.0)})
    assert walker.x == pytest.approx(start + WALK_SPEED * 0.1)
    run(battle, seconds=20.0, intents={walker.soldier_id: Intent(move=-1.0)})
    assert walker.x == 0.0
    run(battle, seconds=30.0, intents={walker.soldier_id: Intent(move=1.0)})
    assert walker.x == FIELD_WIDTH - 1


def test_walkers_follow_the_ground():
    """A soldier's feet stay on the ground as it rises under them."""
    ground = tuple(FLAT_GROUND_Y - x * 0.1 for x in range(FIELD_WIDTH))
    terrain = Terrain(width=FIELD_WIDTH, height=FIELD_HEIGHT, ground=ground)
    battle = Battle(terrain=terrain, soldiers_per_side=1, sandbag_xs=())
    walker = battle.living(Side.PLATOON)[0]
    run(battle, seconds=1.0, intents={walker.soldier_id: Intent(move=1.0)})
    assert walker.y == pytest.approx(terrain.ground_y(walker.x))


def test_aim_is_stored_and_missing_intents_stand_still():
    """The aim from an intent is kept; soldiers without an intent do nothing."""
    battle = flat_battle(soldiers_per_side=1)
    platoon, brigade = battle.soldiers
    brigade_start = (brigade.x, brigade.aim_angle)
    battle.step(dt=0.1, intents={platoon.soldier_id: Intent(aim_angle=1.0)})
    assert platoon.aim_angle == 1.0
    assert (brigade.x, brigade.aim_angle) == brigade_start
    assert battle.seconds == pytest.approx(0.1)


def test_dead_soldiers_ignore_their_intents():
    """A dead soldier cannot walk, aim or fire."""
    battle = flat_battle(soldiers_per_side=1)
    soldier = battle.soldiers[0]
    soldier.health = 0
    start = soldier.x
    battle.step(dt=0.1, intents={soldier.soldier_id: Intent(move=1.0, aim_angle=1.0, fire=True)})
    assert soldier.x == start
    assert soldier.aim_angle == 0.0
    assert battle.bullets == []


def test_firing_waits_for_the_cooldown():
    """Holding fire spawns one bullet, then waits out the pistol cooldown."""
    battle, shooter, _target = duel(distance=700)
    intents = {shooter.soldier_id: Intent(fire=True)}
    battle.step(dt=TIME_STEP, intents=intents)
    assert len(battle.bullets) == 1
    assert battle.bullets[0].side is Side.PLATOON
    assert shooter.cooldown > 0.0
    battle.step(dt=TIME_STEP, intents=intents)
    assert len(battle.bullets) == 1  # still only the first bullet


def test_a_bullet_aimed_up_climbs_in_screen_coordinates():
    """Screen y grows downward, so an upward shot has negative vertical velocity."""
    battle, shooter, _target = duel(distance=700)
    battle.step(
        dt=TIME_STEP, intents={shooter.soldier_id: Intent(aim_angle=math.pi / 2, fire=True)}
    )
    bullet = battle.bullets[0]
    assert bullet.velocity_y < 0.0
    assert bullet.velocity_x == pytest.approx(0.0, abs=1e-6)


def test_bullets_stop_at_a_hill():
    """A hill between the duellists swallows the shots."""
    ground = tuple(100.0 if 300 <= x <= 500 else FLAT_GROUND_Y for x in range(FIELD_WIDTH))
    terrain = Terrain(width=FIELD_WIDTH, height=FIELD_HEIGHT, ground=ground)
    battle, shooter, target = duel(distance=600, terrain=terrain)
    run(battle, seconds=2.0, intents={shooter.soldier_id: Intent(fire=True)})
    run(battle, seconds=1.0, intents={})  # let the last bullet fly
    assert target.health == SOLDIER_HEALTH
    assert battle.bullets == []


def test_bullets_leaving_the_field_disappear():
    """A bullet that flies off the edge of the field is gone."""
    battle, shooter, _target = duel(distance=700)
    shooter.x = 50.0
    battle.step(dt=TIME_STEP, intents={shooter.soldier_id: Intent(aim_angle=math.pi, fire=True)})
    run(battle, seconds=1.0, intents={})
    assert battle.bullets == []


def test_out_of_range_shots_fall_away():
    """distance_left runs out at PISTOL_RANGE and the bullet is removed."""
    battle, shooter, target = duel(distance=PISTOL_RANGE + 150)
    battle.step(dt=0.1, intents={shooter.soldier_id: Intent(fire=True)})
    bullet = battle.bullets[0]
    assert bullet.distance_left == pytest.approx(PISTOL_RANGE - 600.0 * 0.1)
    run(battle, seconds=1.0, intents={})
    assert battle.bullets == []
    assert target.health == SOLDIER_HEALTH


def test_a_fast_bullet_cannot_tunnel_through_a_soldier():
    """Even a long time step does not let a bullet skip over its target."""
    battle, shooter, target = duel(distance=200)
    battle.step(dt=0.3, intents={shooter.soldier_id: Intent(fire=True)})
    assert target.health == SOLDIER_HEALTH - 1


def test_two_last_soldiers_shooting_each_other_at_once_is_a_draw():
    """One soldier a side at health 1 fire at each other in the same step: both fall, a draw."""
    battle, shooter, target = duel(distance=200)
    shooter.health = target.health = 1
    intents = {
        shooter.soldier_id: Intent(aim_angle=0.0, fire=True),
        target.soldier_id: Intent(aim_angle=math.pi, fire=True),
    }
    killed_at: dict[int, float] = {}
    for _ in range(round(1.0 / TIME_STEP)):
        for event in battle.step(dt=TIME_STEP, intents=intents):
            assert isinstance(event, SoldierKilled)
            killed_at[event.soldier_id] = battle.seconds
        if battle.over:
            break
    assert killed_at.keys() == {shooter.soldier_id, target.soldier_id}
    assert len(set(killed_at.values())) == 1  # in the same step
    assert battle.over
    assert battle.winner is None


def test_the_battle_is_over_once_either_army_has_fallen():
    """Over with one side gone (a win) or both (a draw); not while both fight."""
    battle = flat_battle(soldiers_per_side=1)
    assert not battle.over
    battle.soldier(1).health = 0
    assert battle.over
    battle.soldier(0).health = 0
    assert battle.over
    battle.soldier(1).health = 1
    assert battle.over


def test_a_soldier_firing_from_cover_never_hits_his_own_sandbag():
    """Level fire from just behind a bag (his muzzle inside it) leaves it full and hits beyond."""
    bag_x = 300.0
    battle, shooter, target = duel(distance=200, sandbag_xs=(bag_x,))
    # His cover spot: a few pixels from the bag's near edge, within his muzzle's reach
    shooter.x = bag_x - SANDBAG_WIDTH / 2 - MUZZLE_DISTANCE / 2
    target.x = shooter.x + 200.0
    assert bag_x - SANDBAG_WIDTH / 2 < shooter.muzzle[0]
    run(
        battle,
        seconds=PISTOL_COOLDOWN + BULLET_FLIGHT_SLACK_SECONDS,
        intents={shooter.soldier_id: Intent(aim_angle=0.0, fire=True)},
    )
    assert battle.sandbags[0].sand == 1.0
    assert target.health == SOLDIER_HEALTH - 2 * PISTOL_DAMAGE


def test_a_bullet_ignores_only_the_sandbags_its_shooter_stood_by():
    """His own cover is judged when he fires: a bag farther than his muzzle's reach is hit."""
    near_x = 300.0
    battle, shooter, _target = duel(distance=400, sandbag_xs=(near_x, near_x + 150.0))
    shooter.x = near_x - SANDBAG_WIDTH / 2 - MUZZLE_DISTANCE
    battle.step(dt=TIME_STEP, intents={shooter.soldier_id: Intent(aim_angle=0.0, fire=True)})
    assert battle.bullets[0].ignored_sandbags == frozenset({0})
    run(battle, seconds=1.0, intents={})
    assert battle.sandbags[0].sand == 1.0
    assert battle.sandbags[1].sand == 1.0 - SAND_PER_HIT
    shooter.x = near_x - SANDBAG_WIDTH / 2 - MUZZLE_DISTANCE - 1.0
    shooter.cooldown = 0.0
    battle.step(dt=TIME_STEP, intents={shooter.soldier_id: Intent(aim_angle=0.0, fire=True)})
    # A pixel farther back, the bag is beyond his muzzle: the shot hits it at once
    assert not battle.bullets
    assert battle.sandbags[0].sand == 1.0 - SAND_PER_HIT


def test_the_winner_is_the_army_left_standing():
    """The winner is None until one side has no living soldiers."""
    battle = flat_battle(soldiers_per_side=2)
    assert battle.winner is None
    for soldier in battle.living(Side.BRIGADE):
        soldier.health = 0
        assert battle.winner is (None if soldier.soldier_id == 2 else Side.PLATOON)
    assert battle.winner is Side.PLATOON
    for soldier in battle.living(Side.PLATOON):
        soldier.health = 0
    assert battle.winner is None  # nobody left: a draw
    battle.soldier(2).health = 1
    assert battle.winner is Side.BRIGADE


def test_sandbag_positions_sit_on_each_half_away_from_the_spawn_fifths():
    """Two or three sandbags per side, seeded, between the spawn fifth and the middle."""
    terrain = build_terrain(width=FIELD_WIDTH, height=FIELD_HEIGHT, random=random.Random(3))
    seen_counts = set()
    for seed in range(20):
        positions = sandbag_positions(terrain=terrain, random=random.Random(seed))
        assert positions == sandbag_positions(terrain=terrain, random=random.Random(seed))
        left = [x for x in positions if x < terrain.width / 2]
        right = [x for x in positions if x >= terrain.width / 2]
        assert 2 <= len(left) <= 3
        assert 2 <= len(right) <= 3
        seen_counts.update({len(left), len(right)})
        assert all(terrain.width / 5 <= x for x in left)
        assert all(x <= terrain.width * 4 / 5 for x in right)
        assert list(positions) == sorted(positions)
    assert seen_counts == {2, 3}


def test_sandbag_defaults():
    """A new sandbag is full and standing."""
    bag = Sandbag(x=10.0, width=SANDBAG_WIDTH, sand=1.0)
    assert not bag.flattened
    bag.sand = 0.0
    assert bag.flattened


def test_sandbags_avoid_a_steep_ramp_when_there_is_level_ground():
    """A bag is not laid across a steep ramp when its slot has level ground to choose instead."""
    ramp_start, ramp_end = 190, 215
    ground = tuple(
        400.0 - min(max(x - ramp_start, 0), ramp_end - ramp_start) * 2.0 for x in range(FIELD_WIDTH)
    )
    terrain = Terrain(width=FIELD_WIDTH, height=FIELD_HEIGHT, ground=ground)
    for seed in range(20):
        positions = sandbag_positions(terrain=terrain, random=random.Random(seed))
        assert positions == sandbag_positions(terrain=terrain, random=random.Random(seed))
        for x in positions:
            heights = [
                terrain.ground_y(float(column))
                for column in range(round(x - SANDBAG_WIDTH / 2), round(x + SANDBAG_WIDTH / 2) + 1)
            ]
            assert max(heights) - min(heights) <= SANDBAG_MAX_GROUND_VARIATION


def test_sandbags_take_the_flattest_spot_when_none_is_level():
    """With only slope to choose from, the bag still lands in its slot, on the gentlest part."""
    # Every column is steeper than the limit, steeper still toward the middle of the field
    ground = tuple(400.0 - abs(x - 400) * 2.0 for x in range(FIELD_WIDTH))
    terrain = Terrain(width=FIELD_WIDTH, height=FIELD_HEIGHT, ground=ground)
    positions = sandbag_positions(terrain=terrain, random=random.Random(5))
    assert len(positions) >= 4
    assert all(terrain.width / 5 <= x <= terrain.width * 4 / 5 for x in positions)
