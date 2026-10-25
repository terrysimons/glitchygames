"""The computer driver: it looks at the battle and produces an ``Intent`` for one soldier.

Every driver produces an ``Intent`` and the battle applies it the same way, so nothing here
touches the rules. The computer's randomness (aim error and reaction delay) comes only from the
``random`` stream passed in, which is that one soldier's own stream.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from glitchygames.examples.drawing_fire.battle import (
    PISTOL_RANGE,
    SOLDIER_CHEST_HEIGHT,
    Battle,
    Intent,
    Sandbag,
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
# A soldier advances until the enemy is within this fraction of the pistol range
ADVANCE_RANGE_FRACTION = 0.8
# A soldier heads for a standing sandbag on his way when it is this near (px)...
SANDBAG_SEEK_DISTANCE = 90.0
# ...and stops once he is this close to its near edge (px)
SANDBAG_COVER_DISTANCE = 8.0
# The ground between two soldiers is checked this often along the line of fire (px)
LINE_OF_SIGHT_STEP = 6.0


@dataclass
class ComputerSoldier:
    """What the computer remembers about one soldier: his target and when he may shoot it."""

    target_id: int | None = None
    # Battle seconds when the reaction delay for the current target has passed
    fire_ready_at: float = 0.0


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
    minds = {soldier.soldier_id: ComputerSoldier() for soldier in battle.soldiers}
    streams = {
        soldier.soldier_id: random_stream(
            soldier_stream_name(battle_number=battle_number, soldier_id=soldier.soldier_id)
        )
        for soldier in battle.soldiers
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
    target = min(
        enemies,
        key=lambda enemy: math.hypot(enemy.chest[0] - chest_x, enemy.chest[1] - chest_y),
    )
    if mind.target_id != target.soldier_id:
        # A new target: the reaction delay starts now
        mind.target_id = target.soldier_id
        mind.fire_ready_at = battle.seconds + random.uniform(*REACTION_SECONDS_RANGE)

    target_x, target_y = target.chest
    distance = math.hypot(target_x - chest_x, target_y - chest_y)
    direction = 1.0 if target_x > chest_x else -1.0
    # A hill between them stops every bullet, so he neither stands nor fires until he sees him
    can_see = _can_see(terrain=battle.terrain, start=soldier.chest, end=target.chest)
    cover = _nearest_cover(soldier=soldier, battle=battle, direction=direction)
    ready = soldier.cooldown <= 0.0 and battle.seconds >= mind.fire_ready_at

    # A standing sandbag right in his way and a hill hiding the enemy beyond it: he shoots the
    # sandbag until it is low enough to walk over
    if cover is not None and not can_see and cover[1] <= SANDBAG_COVER_DISTANCE:
        middle_y = battle.terrain.ground_y(cover[0].x) - cover[0].height / 2
        aim_angle = math.atan2(chest_y - middle_y, cover[0].x - chest_x)
        return Intent(move=0.0, aim_angle=aim_angle, fire=ready)

    # Screen y grows downward, so a target above is a positive angle
    bearing = math.atan2(chest_y - target_y, target_x - chest_x)
    return Intent(
        move=_movement(
            distance=distance,
            can_see=can_see,
            direction=direction,
            cover_distance=None if cover is None else cover[1],
        ),
        aim_angle=bearing + random.gauss(0.0, AIM_ERROR_RADIANS),
        fire=ready and can_see and distance <= PISTOL_RANGE,
    )


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


def _movement(
    *, distance: float, can_see: bool, direction: float, cover_distance: float | None
) -> float:
    """Decide how a soldier walks: toward the enemy until in range, via cover on the way.

    Args:
        distance: How far the target is.
        can_see: Whether the ground leaves a clear line to the target.
        direction: -1 toward the left, 1 toward the right (where the target is).
        cover_distance: How far the covering sandbag on his way is (None when there is none).

    Returns:
        The move for his intent: the direction, or 0 to stand.

    """
    if can_see and distance <= PISTOL_RANGE * ADVANCE_RANGE_FRACTION:
        return 0.0
    # Stop behind cover only once the enemy is in range, so cover is never a place to hide
    # from a fight that is too far away to start
    if cover_distance is not None and can_see and distance <= PISTOL_RANGE:
        return 0.0 if cover_distance <= SANDBAG_COVER_DISTANCE else direction
    return direction


def _nearest_cover(
    *, soldier: Soldier, battle: Battle, direction: float
) -> tuple[Sandbag, float] | None:
    """Find the sandbag that covers a soldier on his way, and how far its near edge is.

    Only a sandbag tall enough to cover a soldier's chest counts, and only one ahead of him
    (or around him, when he is already behind it) within ``SANDBAG_SEEK_DISTANCE``.

    Args:
        soldier: The soldier.
        battle: The battle.
        direction: -1 toward the left, 1 toward the right (where the enemy is).

    Returns:
        The nearest such sandbag and the distance to its near edge (0 when he is already at or
        inside it), or None when no covering sandbag is near.

    """
    nearest: tuple[Sandbag, float] | None = None
    for sandbag in battle.sandbags:
        if sandbag.height <= SOLDIER_CHEST_HEIGHT:
            continue
        distance = _distance_to_near_edge(sandbag=sandbag, x=soldier.x, direction=direction)
        if (
            distance is not None
            and distance <= SANDBAG_SEEK_DISTANCE
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
