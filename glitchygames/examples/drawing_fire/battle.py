"""The battle model: soldiers, pistols, bullets, sandbags and the winner.

This module is pure: no pygame, no drawing, no randomness and no clock. Time only
comes from the ``dt`` passed to ``Battle.step``, and every driver (computer or human)
steers a soldier the same way, with an ``Intent``.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from random import Random

    from glitchygames.examples.drawing_fire.terrain import Terrain

SOLDIERS_PER_SIDE = 8
SOLDIER_HEALTH = 6
WALK_SPEED = 60.0  # px/s
PISTOL_COOLDOWN = 1.5  # s
BULLET_SPEED = 600.0  # px/s
PISTOL_RANGE = 420.0  # px
PISTOL_DAMAGE = 1
SOLDIER_HIT_RADIUS = 9.0  # px
SANDBAG_HEIGHT = 34.0  # px
SANDBAG_WIDTH = 48.0  # px
SAND_PER_HIT = 0.25

# A soldier stands this tall (px); a sandbag at least half of it blocks walking
SOLDIER_HEIGHT = 40.0
# The chest, where the pistol is held and where bullets hit, is this far above the feet (px)
SOLDIER_CHEST_HEIGHT = 20.0
# The muzzle is this far out from the chest along the aim (px)
MUZZLE_DISTANCE = 12.0
# Each army spawns in this fraction of the field width, at its own edge
SPAWN_FRACTION = 1 / 5
# Sandbags come in this many per side
SANDBAGS_PER_SIDE_RANGE = (2, 3)
# A bullet is checked this often along its path (px), so a long time step cannot tunnel
BULLET_CHECK_DISTANCE = SOLDIER_HIT_RADIUS / 2


class Side(enum.StrEnum):
    """The two armies."""

    PLATOON = 'platoon'
    BRIGADE = 'brigade'

    @property
    def opponent(self) -> Side:
        """The other army."""
        return Side.BRIGADE if self is Side.PLATOON else Side.PLATOON


ARMY_NAMES = {Side.PLATOON: 'Pencil Platoon', Side.BRIGADE: 'Graphite Brigade'}


@dataclass(frozen=True)
class Intent:
    """What one soldier wants to do this step, whoever is driving it."""

    # -1 is full speed left, 1 is full speed right
    move: float = 0.0
    # Radians: 0 points right, math.pi / 2 points up
    aim_angle: float = 0.0
    fire: bool = False


@dataclass
class Soldier:
    """A stick-figure soldier."""

    soldier_id: int
    side: Side
    x: float
    y: float  # the feet, on the ground
    health: int
    aim_angle: float
    cooldown: float

    @property
    def alive(self) -> bool:
        """Whether the soldier is still standing."""
        return self.health > 0

    @property
    def chest(self) -> tuple[float, float]:
        """Where the soldier is hit and where the pistol is held."""
        return (self.x, self.y - SOLDIER_CHEST_HEIGHT)

    @property
    def muzzle(self) -> tuple[float, float]:
        """Where the bullets leave the pistol: out from the chest along the aim."""
        chest_x, chest_y = self.chest
        # Screen y grows downward, so aiming up (positive sine) lowers y
        return (
            chest_x + MUZZLE_DISTANCE * math.cos(self.aim_angle),
            chest_y - MUZZLE_DISTANCE * math.sin(self.aim_angle),
        )


@dataclass
class Sandbag:
    """A sandbag wall that loses sand when shot and flattens."""

    x: float
    width: float
    sand: float  # 1.0 full .. 0.0 flat

    @property
    def height(self) -> float:
        """How tall the sandbag stands now."""
        return SANDBAG_HEIGHT * self.sand

    @property
    def blocks_walking(self) -> bool:
        """Whether the sandbag is tall enough (at least half a soldier) to stop a walk.

        The computer driver uses this same rule for "tall enough to cover a soldier".
        """
        return self.height >= SOLDIER_HEIGHT / 2

    @property
    def flattened(self) -> bool:
        """Whether all the sand is gone."""
        return self.sand <= 0.0


@dataclass
class Bullet:
    """A pistol bullet in flight."""

    x: float
    y: float
    velocity_x: float
    velocity_y: float
    side: Side
    distance_left: float


@dataclass(frozen=True)
class SoldierKilled:
    """A soldier's health reached zero."""

    soldier_id: int


@dataclass(frozen=True)
class SandbagFlattened:
    """A sandbag lost its last sand."""

    index: int


type BattleEvent = SoldierKilled | SandbagFlattened


def sandbag_positions(*, terrain: Terrain, random: Random) -> tuple[float, ...]:
    """Choose where the sandbags go: two or three per side, away from the spawn fifths.

    Each side's stretch (from just past its spawn fifth to the middle) is cut into one
    slot per sandbag, so the sandbags never overlap.

    Args:
        terrain: The ground the sandbags go on.
        random: The seeded stream the positions are drawn from.

    Returns:
        The sandbags' x positions, from left to right.

    """
    half_width = SANDBAG_WIDTH / 2
    stretch_start = terrain.width * SPAWN_FRACTION + half_width
    stretch_end = terrain.width / 2 - half_width
    positions: list[float] = []
    for side in Side:
        count = random.randint(*SANDBAGS_PER_SIDE_RANGE)
        slot_width = (stretch_end - stretch_start) / count
        for slot in range(count):
            position = random.uniform(
                stretch_start + slot * slot_width, stretch_start + (slot + 1) * slot_width
            )
            # Brigade's stretch mirrors Platoon's
            positions.append(position if side is Side.PLATOON else terrain.width - position)
    return tuple(sorted(positions))


class Battle:
    """The whole battle: two armies, the sandbags, the bullets in flight and the clock."""

    def __init__(
        self, *, terrain: Terrain, soldiers_per_side: int, sandbag_xs: Sequence[float]
    ) -> None:
        """Muster both armies and lay the sandbags.

        Args:
            terrain: The ground everything stands on.
            soldiers_per_side: How many soldiers each army has.
            sandbag_xs: The x positions of the sandbags.

        """
        self.terrain = terrain
        self.soldiers: list[Soldier] = []
        self.sandbags = [Sandbag(x=x, width=SANDBAG_WIDTH, sand=1.0) for x in sandbag_xs]
        self.bullets: list[Bullet] = []
        self.seconds = 0.0

        fifth = terrain.width * SPAWN_FRACTION
        for side in Side:
            fifth_start = 0.0 if side is Side.PLATOON else terrain.width - fifth
            facing = 0.0 if side is Side.PLATOON else math.pi
            for index in range(soldiers_per_side):
                # Spread evenly through the fifth, never on its edges
                x = fifth_start + fifth * (index + 0.5) / soldiers_per_side
                self.soldiers.append(
                    Soldier(
                        soldier_id=len(self.soldiers),
                        side=side,
                        x=x,
                        y=terrain.ground_y(x),
                        health=SOLDIER_HEALTH,
                        aim_angle=facing,
                        cooldown=0.0,
                    )
                )

    def living(self, side: Side) -> list[Soldier]:
        """Find an army's soldiers who are still standing.

        Args:
            side: The army.

        Returns:
            The living soldiers, in id order.

        """
        return [soldier for soldier in self.soldiers if soldier.side is side and soldier.alive]

    def soldier(self, soldier_id: int) -> Soldier:
        """Find a soldier by id.

        Args:
            soldier_id: The soldier's id.

        Returns:
            The soldier.

        """
        return self.soldiers[soldier_id]

    @property
    def winner(self) -> Side | None:
        """The side with soldiers left when the other has none (None while both fight)."""
        platoon_alive = bool(self.living(Side.PLATOON))
        brigade_alive = bool(self.living(Side.BRIGADE))
        if platoon_alive and not brigade_alive:
            return Side.PLATOON
        if brigade_alive and not platoon_alive:
            return Side.BRIGADE
        return None

    def step(self, *, dt: float, intents: Mapping[int, Intent]) -> list[BattleEvent]:
        """Advance the battle: apply every intent, then fly the bullets.

        Soldiers and bullets are processed in list order, so the same inputs always give
        the same battle.

        Args:
            dt: The seconds to advance.
            intents: What each soldier wants to do, by soldier id (missing ones stand still).

        Returns:
            What happened this step.

        """
        self.seconds += dt
        events: list[BattleEvent] = []
        for soldier in self.soldiers:
            if soldier.alive:
                soldier.cooldown = max(0.0, soldier.cooldown - dt)
                # A soldier without an intent stands still, keeping the aim it had
                intent = intents.get(soldier.soldier_id)
                if intent is not None:
                    self._apply_intent(soldier, intent, dt=dt)
        self.bullets = [
            bullet for bullet in self.bullets if not self._fly(bullet, dt=dt, events=events)
        ]
        return events

    def _apply_intent(self, soldier: Soldier, intent: Intent, *, dt: float) -> None:
        """Walk, aim and maybe fire one soldier's pistol."""
        move = min(max(intent.move, -1.0), 1.0)
        target_x = soldier.x + move * WALK_SPEED * dt
        target_x = min(max(target_x, 0.0), float(self.terrain.width - 1))
        soldier.x = self._stop_at_sandbags(soldier.x, target_x)
        soldier.y = self.terrain.ground_y(soldier.x)
        soldier.aim_angle = intent.aim_angle
        if intent.fire and soldier.cooldown <= 0.0:
            muzzle_x, muzzle_y = soldier.muzzle
            self.bullets.append(
                Bullet(
                    x=muzzle_x,
                    y=muzzle_y,
                    velocity_x=BULLET_SPEED * math.cos(soldier.aim_angle),
                    # Screen y grows downward, so aiming up gives negative velocity
                    velocity_y=-BULLET_SPEED * math.sin(soldier.aim_angle),
                    side=soldier.side,
                    distance_left=PISTOL_RANGE,
                )
            )
            soldier.cooldown = PISTOL_COOLDOWN

    def _stop_at_sandbags(self, start_x: float, target_x: float) -> float:
        """Stop a walk at the edge of a sandbag that is tall enough to block it.

        Args:
            start_x: Where the walk starts.
            target_x: Where the walk would end.

        Returns:
            Where the walk really ends.

        """
        stopped_x = target_x
        for sandbag in self.sandbags:
            if not sandbag.blocks_walking:
                continue
            left_edge = sandbag.x - sandbag.width / 2
            right_edge = sandbag.x + sandbag.width / 2
            # Only a walk that starts outside the sandbag and reaches it is stopped, so a
            # soldier already standing inside one can still walk out
            if start_x <= left_edge < stopped_x:
                stopped_x = left_edge
            elif start_x >= right_edge > stopped_x:
                stopped_x = right_edge
        return stopped_x

    def _fly(self, bullet: Bullet, *, dt: float, events: list[BattleEvent]) -> bool:
        """Move a bullet along its path.

        Args:
            bullet: The bullet.
            dt: The seconds to fly.
            events: Where to add what the bullet hits.

        Returns:
            Whether the bullet is spent.

        """
        distance = min(BULLET_SPEED * dt, bullet.distance_left)
        checks = max(1, math.ceil(distance / BULLET_CHECK_DISTANCE))
        check_distance = distance / checks
        direction_x = bullet.velocity_x / BULLET_SPEED
        direction_y = bullet.velocity_y / BULLET_SPEED
        for _ in range(checks):
            bullet.x += direction_x * check_distance
            bullet.y += direction_y * check_distance
            bullet.distance_left -= check_distance
            if self._bullet_is_spent(bullet, events=events):
                return True
        return bullet.distance_left <= 0.0

    def _bullet_is_spent(self, bullet: Bullet, *, events: list[BattleEvent]) -> bool:
        """Check a bullet against the field, the ground, the sandbags and the enemy.

        Args:
            bullet: The bullet.
            events: Where to add what the bullet hits.

        Returns:
            Whether the bullet hit something and is spent.

        """
        if not 0.0 <= bullet.x <= self.terrain.width - 1:
            return True
        if bullet.y >= self.terrain.ground_y(bullet.x):
            return True
        for index, sandbag in enumerate(self.sandbags):
            if self._sandbag_is_hit(bullet, sandbag):
                sandbag.sand = max(0.0, sandbag.sand - SAND_PER_HIT)
                if sandbag.flattened:
                    events.append(SandbagFlattened(index=index))
                return True
        for soldier in self.living(bullet.side.opponent):
            chest_x, chest_y = soldier.chest
            if math.hypot(bullet.x - chest_x, bullet.y - chest_y) <= SOLDIER_HIT_RADIUS:
                soldier.health = max(0, soldier.health - PISTOL_DAMAGE)
                if not soldier.alive:
                    events.append(SoldierKilled(soldier_id=soldier.soldier_id))
                return True
        return False

    def _sandbag_is_hit(self, bullet: Bullet, sandbag: Sandbag) -> bool:
        """Check whether a bullet is inside a standing sandbag.

        Args:
            bullet: The bullet.
            sandbag: The sandbag.

        Returns:
            Whether the bullet is inside it.

        """
        if sandbag.flattened:
            return False
        if abs(bullet.x - sandbag.x) > sandbag.width / 2:
            return False
        return bullet.y >= self.terrain.ground_y(sandbag.x) - sandbag.height
