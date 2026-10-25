"""The computer driver: it looks at the battle and produces an ``Intent`` for one soldier.

Every driver produces an ``Intent`` and the battle applies it the same way, so nothing here
touches the rules. The computer's randomness (aim error, drawn once per shot, and reaction
delay) comes only from the ``random`` stream passed in, which is that one soldier's own stream.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from glitchygames.examples.drawing_fire.battle import (
    PISTOL_RANGE,
    Battle,
    Intent,
    Sandbag,
    Side,
    Soldier,
    sandbag_positions,
)
from glitchygames.examples.drawing_fire.terrain import build_terrain
from glitchygames.randomness import random_stream

if TYPE_CHECKING:
    from random import Random

    from glitchygames.examples.drawing_fire.terrain import Terrain

# Standard deviation (radians) of the aim error, drawn from a normal distribution
AIM_ERROR_RADIANS = 0.08
# Seconds a soldier takes to start shooting at a new target, drawn per new target
REACTION_SECONDS_RANGE = (0.15, 0.45)
# A soldier advances until the enemy is within this fraction of the pistol range (the default
# stand-off; each soldier in a battle draws his own from STAND_OFF_FRACTION_RANGE)
ADVANCE_RANGE_FRACTION = 0.8
STAND_OFF_FRACTION_RANGE = (0.6, 0.9)
# He keeps his target unless another enemy is nearer by more than this (px), so two enemies at
# almost the same distance cannot flip his target (and restart his reaction delay) every frame
TARGET_SWITCH_MARGIN = 30.0
# A soldier heads for a standing sandbag on his way when it is this near (px)...
SANDBAG_SEEK_DISTANCE = 90.0
# ...and stops once he is this close to its near edge (px)
SANDBAG_COVER_DISTANCE = 8.0
# Soldiers of one army stand at least this far apart (px): a soldier crowded by a friend of
# higher priority walks on, and a queue behind a sandbag forms this far apart, so an army
# never piles onto one spot
SOLDIER_SPACING = 16.0
# An enemy this near (px) is on top of a soldier: a crowded soldier steps back instead of on
MELEE_PIXELS = 3 * SOLDIER_SPACING
# Which way each army's enemy side of the field lies: the Platoon musters on the left
TOWARD_ENEMY_SIDE: dict[Side, float] = {Side.PLATOON: 1.0, Side.BRIGADE: -1.0}
# The ground between two soldiers is checked this often along the line of fire (px)
LINE_OF_SIGHT_STEP = 6.0


@dataclass
class ComputerSoldier:
    """What the computer remembers about one soldier: his target and when he may shoot it."""

    target_id: int | None = None
    # Battle seconds when the reaction delay for the current target has passed
    fire_ready_at: float = 0.0
    # He advances until the enemy is within this fraction of the pistol range
    stand_off_fraction: float = ADVANCE_RANGE_FRACTION
    # The aim error (radians) for the current shot: drawn once per shot and held between shots,
    # so the aim (and the arm drawn along it) does not shake every frame
    aim_error: float = 0.0
    # Which way he walks to get off a friend's spot: chosen when he becomes crowded and kept
    # until he is clear, so he does not turn back and forth at the edge of the crowd
    crowd_direction: float | None = None


def soldier_stream_name(*, battle_number: int, soldier_id: int) -> str:
    """Name a soldier's own random stream, so a seat changing hands never shifts another's.

    Args:
        battle_number: Which battle (1 first).
        soldier_id: The soldier's id.

    Returns:
        The stream name for ``glitchygames.randomness.random_stream``.

    """
    return f'drawing_fire.soldier.{battle_number}.{soldier_id}'


def muster_battle(
    *, battle_number: int, width: int, height: int, soldiers_per_side: int
) -> tuple[Battle, dict[int, ComputerSoldier], dict[int, Random]]:
    """Build a battle and a computer driver (memory and random stream) for every soldier.

    Args:
        battle_number: Which battle (1 first).
        width: The field's width in pixels.
        height: The field's height in pixels.
        soldiers_per_side: How many soldiers each army has.

    Returns:
        The battle, each soldier's memory by id and each soldier's random stream by id.

    """
    terrain = build_terrain(
        width=width, height=height, random=random_stream('drawing_fire.terrain')
    )
    sandbag_xs = sandbag_positions(terrain=terrain, random=random_stream('drawing_fire.sandbags'))
    battle = Battle(terrain=terrain, soldiers_per_side=soldiers_per_side, sandbag_xs=sandbag_xs)
    streams = {
        soldier.soldier_id: random_stream(
            soldier_stream_name(battle_number=battle_number, soldier_id=soldier.soldier_id)
        )
        for soldier in battle.soldiers
    }
    # Each soldier draws his own stand-off once, from his own stream, so an army spreads out
    minds = {
        soldier_id: ComputerSoldier(stand_off_fraction=stream.uniform(*STAND_OFF_FRACTION_RANGE))
        for soldier_id, stream in streams.items()
    }
    return battle, minds, streams


def computer_intents(
    *, battle: Battle, minds: dict[int, ComputerSoldier], streams: dict[int, Random]
) -> dict[int, Intent]:
    """Ask the computer what every living soldier wants to do.

    Args:
        battle: The battle.
        minds: Each soldier's memory by id.
        streams: Each soldier's random stream by id.

    Returns:
        Each living soldier's intent by id.

    """
    return {
        soldier.soldier_id: computer_intent(
            soldier=soldier,
            battle=battle,
            random=streams[soldier.soldier_id],
            mind=minds[soldier.soldier_id],
        )
        for soldier in battle.soldiers
        if soldier.alive
    }


def computer_intent(
    *, soldier: Soldier, battle: Battle, random: Random, mind: ComputerSoldier
) -> Intent:
    """Decide what one soldier does: target the nearest enemy, close in, take cover and shoot.

    Args:
        soldier: The soldier being driven.
        battle: The battle he is in.
        random: His own random stream (the only randomness used).
        mind: His memory, updated here.

    Returns:
        His intent. With no living enemy he stands still.

    """
    enemies = battle.living(soldier.side.opponent)
    if not enemies:
        return Intent(move=0.0, aim_angle=soldier.aim_angle, fire=False)
    chest_x, chest_y = soldier.chest
    target = _choose_target(soldier=soldier, battle=battle, enemies=enemies, mind=mind)
    if mind.target_id != target.soldier_id:
        # A new target: the reaction delay starts now
        mind.target_id = target.soldier_id
        mind.fire_ready_at = battle.seconds + random.uniform(*REACTION_SECONDS_RANGE)
        mind.aim_error = random.gauss(0.0, AIM_ERROR_RADIANS)

    target_x, target_y = target.chest
    distance = math.hypot(target_x - chest_x, target_y - chest_y)
    direction = 1.0 if target_x > chest_x else -1.0
    # A hill between them stops every bullet, so he neither stands nor fires until he sees him
    can_see = _can_see(terrain=battle.terrain, start=soldier.chest, end=target.chest)
    cover = _nearest_cover(soldier=soldier, battle=battle, direction=direction)
    ready = soldier.cooldown <= 0.0 and battle.seconds >= mind.fire_ready_at
    _update_crowding(
        soldier=soldier, battle=battle, mind=mind, direction=direction, target_x=target_x
    )

    # A standing sandbag right in his way and the enemy hidden by a hill or too far to shoot: he
    # shoots the sandbag until it is low enough to walk over
    if (
        cover is not None
        and (not can_see or distance > PISTOL_RANGE)
        and cover[1] <= SANDBAG_COVER_DISTANCE
    ):
        middle_y = battle.terrain.ground_y(cover[0].x) - cover[0].height / 2
        # Every shot, at a sandbag or a soldier, is aimed with the held error and then redraws it
        aim_angle = math.atan2(chest_y - middle_y, cover[0].x - chest_x) + mind.aim_error
        if ready:
            mind.aim_error = random.gauss(0.0, AIM_ERROR_RADIANS)
        return Intent(move=0.0, aim_angle=aim_angle, fire=ready)

    # Screen y grows downward, so a target above is a positive angle
    bearing = math.atan2(chest_y - target_y, target_x - chest_x)
    fire = ready and can_see and distance <= PISTOL_RANGE
    aim_angle = bearing + mind.aim_error
    if fire:
        # This shot used the held error; the next shot gets a new one
        mind.aim_error = random.gauss(0.0, AIM_ERROR_RADIANS)
    return Intent(
        move=_movement(
            distance=distance,
            stand_off_distance=PISTOL_RANGE * mind.stand_off_fraction,
            can_see=can_see,
            direction=direction,
            cover_distance=None if cover is None else cover[1],
            queued=_is_queued(soldier=soldier, battle=battle, direction=direction),
            crowded_move=mind.crowd_direction,
        ),
        aim_angle=aim_angle,
        fire=fire,
    )


def _choose_target(
    *, soldier: Soldier, battle: Battle, enemies: list[Soldier], mind: ComputerSoldier
) -> Soldier:
    """Pick the nearest enemy, but stay on the current target unless another is clearly nearer.

    Args:
        soldier: The soldier being driven.
        battle: The battle.
        enemies: The living enemies (not empty).
        mind: His memory, holding his current target.

    Returns:
        The target.

    """
    chest = soldier.chest

    def distance_to(enemy: Soldier) -> float:
        return math.hypot(enemy.chest[0] - chest[0], enemy.chest[1] - chest[1])

    nearest = min(enemies, key=distance_to)
    current = None if mind.target_id is None else battle.soldier(mind.target_id)
    if (
        current is not None
        and current.alive
        and _can_see(terrain=battle.terrain, start=chest, end=current.chest)
        and distance_to(nearest) > distance_to(current) - TARGET_SWITCH_MARGIN
    ):
        return current
    return nearest


def _can_see(*, terrain: Terrain, start: tuple[float, float], end: tuple[float, float]) -> bool:
    """Check that no ground rises between two points.

    Args:
        terrain: The ground.
        start: One point (x, y), screen y growing downward.
        end: The other point.

    Returns:
        Whether a straight line from start to end stays above the ground.

    """
    start_x, start_y = start
    end_x, end_y = end
    steps = max(1, math.ceil(abs(end_x - start_x) / LINE_OF_SIGHT_STEP))
    for step in range(1, steps):
        fraction = step / steps
        x = start_x + (end_x - start_x) * fraction
        y = start_y + (end_y - start_y) * fraction
        if y >= terrain.ground_y(x):
            return False
    return True


def _movement(  # ruff: ignore[too-many-arguments] - each is one fact the walk depends on
    *,
    distance: float,
    stand_off_distance: float,
    can_see: bool,
    direction: float,
    cover_distance: float | None,
    queued: bool,
    crowded_move: float | None,
) -> float:
    """Decide how a soldier walks: toward the enemy until in range, via cover on the way.

    Args:
        distance: How far the target is.
        stand_off_distance: How near he walks to the target before he stands.
        can_see: Whether the ground leaves a clear line to the target.
        direction: -1 toward the left, 1 toward the right (where the target is).
        cover_distance: How far the covering sandbag on his way is (None when there is none).
        queued: Whether a friend ahead of him toward that sandbag is within ``SOLDIER_SPACING``,
            so he waits his place in the queue instead of piling onto the friend.
        crowded_move: Which way he walks to get off a friend's spot (None when no friend of
            higher priority is within ``SOLDIER_SPACING`` of him, so he may stand).

    Returns:
        The move for his intent: the direction, or 0 to stand.

    """
    # A soldier queued behind a friend stops in his place whatever he sees, since the sandbag
    # blocks the way
    if queued:
        return 0.0
    at_cover = cover_distance is not None and cover_distance <= SANDBAG_COVER_DISTANCE
    # Crowded, he gets off the spot whatever he sees (or he would turn back and forth where the
    # ground hides the enemy), unless a sandbag at his feet blocks that way
    if crowded_move is not None and not (at_cover and crowded_move == direction):
        return crowded_move
    if can_see and distance <= stand_off_distance:
        return 0.0
    # Stop behind cover only once the enemy is in range, so cover is never a place to hide
    # from a fight that is too far away to start
    if at_cover and can_see and distance <= PISTOL_RANGE:
        return 0.0
    return direction


def _nearest_cover(
    *,
    soldier: Soldier,
    battle: Battle,
    direction: float,
    seek_distance: float = SANDBAG_SEEK_DISTANCE,
) -> tuple[Sandbag, float] | None:
    """Find the sandbag that covers a soldier on his way, and how far its near edge is.

    Only a sandbag tall enough to cover a soldier's chest counts, and only one ahead of him
    (or around him, when he is already behind it) within the seek distance.

    Args:
        soldier: The soldier.
        battle: The battle.
        direction: -1 toward the left, 1 toward the right (where the enemy is).
        seek_distance: How far ahead a sandbag counts (px).

    Returns:
        The nearest such sandbag and the distance to its near edge (0 when he is already at or
        inside it), or None when no covering sandbag is near.

    """
    nearest: tuple[Sandbag, float] | None = None
    for sandbag in battle.sandbags:
        if not sandbag.blocks_walking:
            continue
        distance = _distance_to_near_edge(sandbag=sandbag, x=soldier.x, direction=direction)
        if (
            distance is not None
            and distance <= seek_distance
            and (nearest is None or distance < nearest[1])
        ):
            nearest = (sandbag, distance)
    return nearest


def _distance_to_near_edge(*, sandbag: Sandbag, x: float, direction: float) -> float | None:
    """Measure from x to a sandbag's edge facing the soldier, if the sandbag is ahead of him.

    Args:
        sandbag: The sandbag.
        x: The soldier's x.
        direction: -1 toward the left, 1 toward the right.

    Returns:
        The distance to the near edge (0 when x is already past it, behind the bag's far edge
        excluded), or None when the sandbag is behind him.

    """
    near_edge = sandbag.x - direction * sandbag.width / 2
    far_edge = sandbag.x + direction * sandbag.width / 2
    if (far_edge - x) * direction <= 0:
        return None
    return max(0.0, (near_edge - x) * direction)


def _priority(soldier: Soldier) -> int:
    """Rank a soldier among his army for keeping a spot: lower keeps it, the same for both armies.

    Each army musters its front soldier at the lowest priority number (the Platoon's last id
    and the Brigade's first), so neither army's front is the one that has to give way.

    Args:
        soldier: The soldier.

    Returns:
        His priority number.

    """
    return -soldier.soldier_id if soldier.side is Side.PLATOON else soldier.soldier_id


def _update_crowding(
    *, soldier: Soldier, battle: Battle, mind: ComputerSoldier, direction: float, target_x: float
) -> None:
    """Keep track of whether a higher-priority friend is on the soldier's spot, and his way off.

    The soldier with the higher priority keeps the spot and the other moves on, so two
    soldiers never both give way and never both stay. He walks on toward the enemy (past the
    crest where his friends stopped), unless the enemy is already within ``MELEE_PIXELS`` of
    him, and then he steps back from the enemy. The way is chosen when he becomes crowded and
    kept until he is clear, but crowding never walks him past the enemy's front: once walking
    on toward the enemy's side would take him within ``MELEE_PIXELS`` of the nearest enemy of
    that side's front (or beyond it), he steps back toward his own side instead. Without that,
    a friend he can never get clear of (a player walking on at the same speed) would lead him
    through the enemy's line to the field's edge, and the next friends behind him after.

    Args:
        soldier: The soldier.
        battle: The battle.
        mind: His memory, updated here (``crowd_direction``).
        direction: -1 toward the left, 1 toward the right (where the enemy is).
        target_x: Where his target is.

    """
    crowded = any(
        _priority(friend) < _priority(soldier) and abs(friend.x - soldier.x) < SOLDIER_SPACING
        for friend in battle.living(soldier.side)
    )
    if not crowded:
        mind.crowd_direction = None
        return
    if mind.crowd_direction is None:
        in_melee = abs(target_x - soldier.x) < MELEE_PIXELS
        mind.crowd_direction = -direction if in_melee else direction
    toward_enemy_side = TOWARD_ENEMY_SIDE[soldier.side]
    if (
        mind.crowd_direction == toward_enemy_side
        and _distance_to_enemy_front(soldier=soldier, battle=battle) < MELEE_PIXELS
    ):
        mind.crowd_direction = -toward_enemy_side


def _distance_to_enemy_front(*, soldier: Soldier, battle: Battle) -> float:
    """Measure how far ahead of a soldier the enemy's front stands, toward the enemy's side.

    The front is the living enemy nearest the soldier's own side of the field.

    Args:
        soldier: The soldier (his army has at least one living enemy).
        battle: The battle.

    Returns:
        The distance (px), negative once he is past the front.

    """
    toward_enemy_side = TOWARD_ENEMY_SIDE[soldier.side]
    front_x = min(
        (enemy.x for enemy in battle.living(soldier.side.opponent)),
        key=lambda enemy_x: enemy_x * toward_enemy_side,
    )
    return (front_x - soldier.x) * toward_enemy_side


def _is_queued(*, soldier: Soldier, battle: Battle, direction: float) -> bool:
    """Check whether a friend is just ahead of the soldier on his way to a covering sandbag.

    Ahead means nearer the bag's near edge (a tie goes to the higher priority), and just means
    by less than ``SOLDIER_SPACING``. A friend ahead who has stopped holds the soldier a
    spacing behind.
    The queue reaches back from a sandbag as far as the sandbag is ahead, so a soldier far back
    never walks up onto the friends waiting in front of him.

    Args:
        soldier: The soldier.
        battle: The battle.
        direction: -1 toward the left, 1 toward the right (where the enemy is).

    Returns:
        Whether he waits in a queue (never when no covering sandbag is on his way).

    """
    friends = [friend for friend in battle.living(soldier.side) if friend is not soldier]
    cover = _nearest_cover(
        soldier=soldier,
        battle=battle,
        direction=direction,
        seek_distance=math.inf,
    )
    if cover is None:
        return False
    sandbag, own_distance = cover
    for friend in friends:
        distance = _distance_to_near_edge(sandbag=sandbag, x=friend.x, direction=direction)
        if (
            distance is not None
            and (distance, _priority(friend)) < (own_distance, _priority(soldier))
            and own_distance - distance < SOLDIER_SPACING
        ):
            return True
    return False
