"""The neighborhood: the joined kids walk a yard larger than the screen under one camera.

Feature plan 4 (plans/2026-11-14-zombies-aint-my-neighbors-4-walking.md). Each joined player
walks their own kid with their own device (``controls``); the kids stay inside the yard, and the
group never spreads wider or taller than the screen less a margin, so one camera, aimed at the
middle of the group's bounding box, always shows everyone (arcade co-op). Kids are drawn in
order of their feet. A pad unplugged here takes its kid with it; with nobody left, the game goes
back to the title. Start or P pauses.

Feature plan 5 (plans/2026-11-14-zombies-aint-my-neighbors-5-zombies.md) adds four TVs, one in
each quarter of the yard, that Lawn Zombies pop out of (waits from the named random stream
``zombies_aint_my_neighbors.tv-spawns``; 3 zombies per TV, 10 in all). Zombies shamble toward the
nearest standing kid; a touch knocks the kid out (its player can't move it until it is back up)
and the zombie grabs. TVs and zombies are drawn by their feet with the kids.

Feature plan 6 (plans/2026-11-15-zombies-aint-my-neighbors-6-channel-changer.md) arms the kids
with the Channel Changer: each player's fire (``controls.player_firing``) fires zaps from their
kid's remote. A zap strikes the first zombie or TV it meets (never a kid): a zombie crumbles and
frees its TV's place under the caps at once; a TV takes damage, and a destroyed one shakes the
world and rumbles the pad of the kid whose zap destroyed it. Each frame runs the kids (who fire),
the TVs, the zombies, then the zaps.

Zombies and zaps come from pools built with the scene (``pool.py``; master plan decision 11), so
no sprite file loads mid-game: a zombie's load took 27 to 41 ms. Idle ones are out of every
group; a spawn or a shot takes one and puts it in the yard, and one that has gone is given back.

Built from options alone, as a recording's first scene is, the keyboard plays P1.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Final, override

import pygame

from glitchygames.camera import Camera2D
from glitchygames.effects.shake import Shake, ShakeStyle, ShakeTarget
from glitchygames.input.state import current_input
from glitchygames.randomness import random_stream
from zombies_aint_my_neighbors.art.palettes import KIDS
from zombies_aint_my_neighbors.controls import DEFAULT_DEADZONE, player_direction, player_firing
from zombies_aint_my_neighbors.kid import FIRE_SECONDS, KID_HEIGHT, KID_WIDTH, Kid, MirrorCache
from zombies_aint_my_neighbors.pool import SpritePool
from zombies_aint_my_neighbors.roster import JoinRoster
from zombies_aint_my_neighbors.roster_scene import KEYBOARD_IDENTITY, RosterScene
from zombies_aint_my_neighbors.tv import TV_SIZE, ZOMBIES_IN_ALL, Tv, TvHit, may_spawn
from zombies_aint_my_neighbors.zap import (
    FIZZLE_SECONDS,
    ZAP_RANGE_SECONDS,
    ZAP_SIZE,
    Zap,
    first_struck,
)
from zombies_aint_my_neighbors.zombie import Zombie, touches

if TYPE_CHECKING:
    from zombies_aint_my_neighbors.roster import DeviceIdentity

type Colour = tuple[int, int, int]

# The yard: two screens by two (no tiles until the props BOM)
YARD_WIDTH: Final = 1600
YARD_HEIGHT: Final = 960
# Kids walk this many pixels a second: two and a half kid heights
WALK_SPEED: Final = 120.0
# The group's span is kept inside the screen less this margin on every side
SCREEN_MARGIN: Final = 24
# Where the kids start, around the middle of the yard, by slot (a two-by-two huddle)
_START_OFFSETS: Final[tuple[tuple[int, int], ...]] = ((-40, -30), (8, -30), (-40, 30), (8, 30))
# The lawn, its mown checkerboard and the hedge round the yard's edge
LAWN_COLOUR: Final[Colour] = (98, 128, 72)
LAWN_CHECKER_COLOUR: Final[Colour] = (88, 116, 64)
HEDGE_COLOUR: Final[Colour] = (40, 70, 40)
LAWN_CHECKER_SIZE: Final = 48
HEDGE_THICKNESS: Final = 16
# The yard is drawn under everything (kids' layers are their feet's rows, 0 and up)
YARD_LAYER: Final = -1000
# The TVs' frames (top-left corners): one in the middle of each quarter of the yard
TV_PLACES: Final[tuple[tuple[float, float], ...]] = tuple(
    (
        column * YARD_WIDTH / 2 + YARD_WIDTH / 4 - TV_SIZE / 2,
        row * YARD_HEIGHT / 2 + YARD_HEIGHT / 4 - TV_SIZE / 2,
    )
    for row in (0, 1)
    for column in (0, 1)
)
# The named random stream the TVs' waits come from (randomness: <game>.<purpose>)
TV_SPAWN_STREAM: Final = 'zombies_aint_my_neighbors.tv-spawns'
# Feature plan 6: a destroyed TV's world shake, and the rumble on the destroying kid's pad
TV_DESTROYED_SHAKE: Final = Shake(
    style=ShakeStyle.NOISE, strength=4.0, duration=0.3, frequency=24.0
)
TV_DESTROYED_RUMBLE_LOW: Final = 0.8
TV_DESTROYED_RUMBLE_HIGH: Final = 0.5
TV_DESTROYED_RUMBLE_MILLISECONDS: Final = 300
# The pools (pool.py). Zombies: the 10 the caps allow alive, and room for ones still fading (a
# kill frees its place at once, but the fade lasts 1 s). Zaps: a zap lasts 0.72 s (its flight and
# fizzle) and a kid fires every 0.25 s, so each of the four kids has at most 3 in the air
MAXIMUM_PLAYERS: Final = 4
ZOMBIE_POOL_SIZE: Final = ZOMBIES_IN_ALL + 6
ZAPS_IN_THE_AIR_PER_KID: Final = math.ceil((ZAP_RANGE_SECONDS + FIZZLE_SECONDS) / FIRE_SECONDS)
ZAP_POOL_SIZE: Final = MAXIMUM_PLAYERS * ZAPS_IN_THE_AIR_PER_KID


def draw_yard(surface: pygame.Surface, offset_x: float, offset_y: float) -> None:
    """Draw the visible part of the yard: a mown checkerboard lawn, and the hedge at its edges.

    Checkers, not stripes (the owner, 2026-11-14): stripes only showed movement across them, so
    walking up or down looked like standing still.

    A camera background layer's draw function: it depends only on its arguments (the camera
    calls it again only when the offset changes).

    Args:
        surface: The layer's surface, the screen's size, cleared.
        offset_x: The camera's left edge in the world.
        offset_y: The camera's top edge in the world.

    """
    surface.fill(LAWN_COLOUR)
    width, height = surface.get_size()
    first_column = int(offset_x // LAWN_CHECKER_SIZE)
    first_row = int(offset_y // LAWN_CHECKER_SIZE)
    columns = width // LAWN_CHECKER_SIZE + 2
    rows = height // LAWN_CHECKER_SIZE + 2
    for row in range(first_row, first_row + rows):
        for column in range(first_column, first_column + columns):
            if (row + column) % 2:
                surface.fill(
                    LAWN_CHECKER_COLOUR,
                    pygame.Rect(
                        round(column * LAWN_CHECKER_SIZE - offset_x),
                        round(row * LAWN_CHECKER_SIZE - offset_y),
                        LAWN_CHECKER_SIZE,
                        LAWN_CHECKER_SIZE,
                    ),
                )
    hedges = (
        pygame.Rect(0, 0, YARD_WIDTH, HEDGE_THICKNESS),
        pygame.Rect(0, YARD_HEIGHT - HEDGE_THICKNESS, YARD_WIDTH, HEDGE_THICKNESS),
        pygame.Rect(0, 0, HEDGE_THICKNESS, YARD_HEIGHT),
        pygame.Rect(YARD_WIDTH - HEDGE_THICKNESS, 0, HEDGE_THICKNESS, YARD_HEIGHT),
    )
    for hedge in hedges:
        surface.fill(HEDGE_COLOUR, hedge.move(-round(offset_x), -round(offset_y)))


def _clamp(value: float, *, low: float, high: float) -> float:
    """Return a value inside [low, high].

    Returns:
        The clamped value.

    """
    return max(low, min(high, value))


class NeighborhoodScene(RosterScene):
    """The neighborhood: the joined kids walking a yard."""

    NAME = "Zombies Ain't My Neighbors"
    VERSION = '1.0'

    @override
    def __init__(
        self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
        roster: JoinRoster | dict[str, Any] | None = None,
    ) -> None:
        """Make the neighborhood for the joined players (the keyboard as P1 when none are given).

        Args:
            options: The engine's options.
            groups: The sprite groups to draw into (a new LayeredDirty when None).
            roster: The players: a roster, its JSON form (as a replay passes it back), or None
                for the keyboard alone.

        """
        if roster is None:
            roster = JoinRoster.empty().join(device=KEYBOARD_IDENTITY)
        super().__init__(options=options, groups=groups, roster=roster)
        self.background_color = LAWN_COLOUR
        self.deadzone = float((self.options or {}).get('axis_deadzone', DEFAULT_DEADZONE))
        self.camera = Camera2D(
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            smooth_factor=1.0,
            lead_x=self.screen_width / 2,
            lead_y=self.screen_height / 2,
        )
        self.camera.set_bounds(
            min_x=0,
            min_y=0,
            max_x=YARD_WIDTH - self.screen_width,
            max_y=YARD_HEIGHT - self.screen_height,
        )
        self.mirror_cache = MirrorCache()
        self.kids: dict[int, Kid] = {}
        self._yard_drawn = False
        self.add_missing_kids()
        stream = random_stream(TV_SPAWN_STREAM)
        self.tvs = [
            Tv(world_x=world_x, world_y=world_y, stream=stream, groups=self.all_sprites)
            for world_x, world_y in TV_PLACES
        ]
        for tv in self.tvs:
            tv.dt_tick(0.0)
            self._order_by_feet(tv, height=TV_SIZE)
        self.zombies: list[Zombie] = []
        # Each zombie's TV (one put in by hand has none), whose place it frees when it dies
        self.zombie_homes: dict[Zombie, Tv] = {}
        # The zaps in the air, and the slot of the kid who fired each
        self.zaps: list[Zap] = []
        self.zap_owners: dict[Zap, int] = {}
        self.yard_bounds = pygame.Rect(0, 0, YARD_WIDTH, YARD_HEIGHT)
        # Built now, before play: every zombie and zap the yard will need
        self.zombie_pool = SpritePool(make=self._make_zombie, size=ZOMBIE_POOL_SIZE)
        self.zap_pool = SpritePool(make=self._make_zap, size=ZAP_POOL_SIZE)

    def _make_zombie(self) -> Zombie:
        """Make a zombie for the pool, out of every group.

        Returns:
            The zombie.

        """
        zombie = Zombie(world_x=0.0, world_y=0.0, mirror_cache=self.mirror_cache, groups=None)
        zombie.kill()
        return zombie

    def _make_zap(self) -> Zap:
        """Make a zap for the pool, out of every group.

        Returns:
            The zap.

        """
        zap = Zap(centre=(0.0, 0.0), direction=(1.0, 0.0), bounds=self.yard_bounds, groups=None)
        zap.kill()
        return zap

    @override
    def setup(self) -> None:
        """Lay the yard under the kids (once: setting up again after a pause keeps it)."""
        super().setup()
        if self._yard_drawn:
            return
        self.camera.add_background_layer(
            scroll_factor=1.0,
            draw_function=draw_yard,
            layer_depth=YARD_LAYER,
            groups=self.all_sprites,
        )
        self._yard_drawn = True

    def add_missing_kids(self) -> None:
        """Give every joined slot without a kid its kid, at its place in the starting huddle."""
        for player in self.roster.joined_players:
            if player.slot_index in self.kids:
                continue
            offset_x, offset_y = _START_OFFSETS[player.slot_index]
            kid = Kid(
                look_name=KIDS[player.slot_index].name,
                world_x=float(YARD_WIDTH // 2 + offset_x),
                world_y=float(YARD_HEIGHT // 2 + offset_y),
                mirror_cache=self.mirror_cache,
                groups=self.all_sprites,
            )
            self.kids[player.slot_index] = kid
            self._order_by_feet(kid)

    def add_zombie(self, *, world_x: float, world_y: float, home: Tv | None = None) -> Zombie:
        """Put a Lawn Zombie in the yard.

        Args:
            world_x: Its frame's left edge in the world.
            world_y: Its frame's top edge in the world.
            home: The TV it came out of (it frees that TV's place when it dies), if any.

        Returns:
            The zombie.

        """
        zombie = self.zombie_pool.take()
        zombie.spawn_at(world_x=world_x, world_y=world_y)
        self.all_sprites.add(zombie)
        zombie.dt_tick(0.0)
        self._order_by_feet(zombie)
        self.zombies.append(zombie)
        if home is not None:
            self.zombie_homes[zombie] = home
        return zombie

    def add_zap(self, *, kid: Kid, slot_index: int) -> Zap:
        """Fire a zap from a kid's remote, the kid's way.

        Args:
            kid: The kid who fired (posed this frame, so its remote is in its hand).
            slot_index: The kid's player slot.

        Returns:
            The zap.

        """
        zap = self.zap_pool.take()
        zap.launch(centre=kid.muzzle(), direction=kid.aim())
        self.all_sprites.add(zap)
        self.zaps.append(zap)
        self.zap_owners[zap] = slot_index
        self._order_by_feet(zap, height=ZAP_SIZE)
        return zap

    def _order_by_feet(self, sprite: Kid | Zombie | Tv | Zap, *, height: int = KID_HEIGHT) -> None:
        """Draw a sprite in order of its feet: lower on the screen is in front."""
        self.all_sprites.change_layer(sprite, round(sprite.world_y + height))

    def _order_kid(self, kid: Kid) -> None:
        """Draw a kid by its feet, its remote just in front of it (just behind when facing up)."""
        self._order_by_feet(kid)
        kid_layer = self.all_sprites.get_layer_of_sprite(kid)
        self.all_sprites.change_layer(kid.remote, kid_layer + (1 if kid.remote_in_front else -1))

    @override
    def dt_tick(self, dt: float) -> None:
        """Move each kid by its player's input, keep the group together, pose the kids.

        Args:
            dt: The frame's time, in seconds.

        """
        super().dt_tick(dt)
        snapshot = current_input()
        for player in self.roster.joined_players:
            # Every joined slot has its kid (add_missing_kids; an unplugged slot's kid goes too)
            kid = self.kids[player.slot_index]
            direction_x, direction_y = player_direction(
                snapshot=snapshot, device=player.device, deadzone=self.deadzone
            )
            if not kid.can_move:
                # Knocked out: the player can't move the kid until it is back up
                direction_x = direction_y = 0.0
            self._move(
                kid,
                world_x=kid.world_x + direction_x * WALK_SPEED * dt,
                world_y=kid.world_y + direction_y * WALK_SPEED * dt,
            )
            kid.walk(direction_x=direction_x, direction_y=direction_y)
            fired = kid.pull_trigger(held=player_firing(snapshot=snapshot, device=player.device))
            kid.dt_tick(dt)
            self._order_kid(kid)
            if fired:
                self.add_zap(kid=kid, slot_index=player.slot_index)
        self._run_tvs(dt)
        self._run_zombies(dt)
        self._run_zaps(dt)

    def _run_tvs(self, dt: float) -> None:
        """Tick each TV under the caps, and put out each zombie whose pop has ended."""
        for tv in self.tvs:
            allowed = may_spawn(
                zombies_from_this_tv=tv.zombies,
                zombies_in_all=sum(each.zombies for each in self.tvs),
            )
            if tv.tick_spawning(dt=dt, allowed=allowed):
                world_x, world_y = tv.spawn_point()
                self.add_zombie(world_x=world_x, world_y=world_y, home=tv)
            tv.dt_tick(dt)

    def _run_zombies(self, dt: float) -> None:
        """Move each zombie, knock out each touchable kid it touches, and pose it."""
        kids = list(self.kids.values())
        for zombie in self.zombies:
            zombie.chase(kids=kids, dt=dt)
            for kid in kids:
                if kid.is_touchable and touches(zombie=zombie, kid=kid):
                    kid.knock_out()
                    zombie.grab()
            zombie.dt_tick(dt)
            # A zombie whose fade ended this frame has left its groups: no layer to change
            if not zombie.is_gone:
                self._order_by_feet(zombie)
        for zombie in [zombie for zombie in self.zombies if zombie.is_gone]:
            self.zombie_pool.give_back(zombie)
        self.zombies = [zombie for zombie in self.zombies if not zombie.is_gone]

    def _run_zaps(self, dt: float) -> None:
        """Fly each zap; each strikes the first living zombie or standing TV it meets."""
        for zap in self.zaps:
            zap.dt_tick(dt)
            if not zap.alive():
                # Fizzled out this frame: it has left its groups
                continue
            self._order_by_feet(zap, height=ZAP_SIZE)
            targets: list[Zombie | Tv] = [
                *(zombie for zombie in self.zombies if not zombie.is_dying),
                *(tv for tv in self.tvs if not tv.is_destroyed),
            ]
            struck = first_struck(zap=zap, targets=targets)
            if struck is None:
                continue
            zap.strike()
            if isinstance(struck, Zombie):
                self._zombie_zapped(struck)
            elif struck.zap() is TvHit.DESTROYED:
                self._tv_destroyed(slot_index=self.zap_owners[zap])
        for zap in [zap for zap in self.zaps if not zap.alive()]:
            self.zaps.remove(zap)
            del self.zap_owners[zap]
            self.zap_pool.give_back(zap)

    def _zombie_zapped(self, zombie: Zombie) -> None:
        """Kill a zombie, freeing its TV's place under the caps at once."""
        if zombie.zap():
            home = self.zombie_homes.pop(zombie, None)
            if home is not None:
                home.zombie_left()

    def _tv_destroyed(self, *, slot_index: int) -> None:
        """Shake the world, and rumble the pad of the kid whose zap destroyed the TV."""
        self.shake(TV_DESTROYED_SHAKE, targets=ShakeTarget.WORLD)
        player = next(
            (player for player in self.roster.joined_players if player.slot_index == slot_index),
            None,
        )
        if player is None or player.device.instance_id is None:
            return
        device = self.input_devices.get(instance_id=player.device.instance_id)
        if device is not None:
            device.rumble(
                low_frequency=TV_DESTROYED_RUMBLE_LOW,
                high_frequency=TV_DESTROYED_RUMBLE_HIGH,
                duration_milliseconds=TV_DESTROYED_RUMBLE_MILLISECONDS,
            )

    def _move(self, kid: Kid, *, world_x: float, world_y: float) -> None:
        """Move a kid toward a place, as far as the yard and the group's screen span allow."""
        limit_width = self.screen_width - 2 * SCREEN_MARGIN
        limit_height = self.screen_height - 2 * SCREEN_MARGIN
        others = [other for other in self.kids.values() if other is not kid]
        low_x, high_x = 0.0, float(YARD_WIDTH - KID_WIDTH)
        low_y, high_y = 0.0, float(YARD_HEIGHT - KID_HEIGHT)
        if others:
            # The group (this kid included) must span no more than the limit
            low_x = max(low_x, max(other.world_x for other in others) + KID_WIDTH - limit_width)
            high_x = min(high_x, min(other.world_x for other in others) + limit_width - KID_WIDTH)
            low_y = max(low_y, max(other.world_y for other in others) + KID_HEIGHT - limit_height)
            high_y = min(high_y, min(other.world_y for other in others) + limit_height - KID_HEIGHT)
        kid.world_x = _clamp(world_x, low=low_x, high=max(low_x, high_x))
        kid.world_y = _clamp(world_y, low=low_y, high=max(low_y, high_y))

    @override
    def camera_target(self) -> tuple[float, float] | None:
        """Aim the camera at the middle of the kids' bounding box (the yard's middle with none).

        Returns:
            The world point the screen centres on.

        """
        if not self.kids:
            return (YARD_WIDTH / 2, YARD_HEIGHT / 2)
        kids = self.kids.values()
        left = min(kid.world_x for kid in kids)
        right = max(kid.world_x + KID_WIDTH for kid in kids)
        top = min(kid.world_y for kid in kids)
        bottom = max(kid.world_y + KID_HEIGHT for kid in kids)
        return ((left + right) / 2, (top + bottom) / 2)

    @override
    def _press_start(self, *, device: DeviceIdentity) -> None:
        """Start pauses the game.

        Args:
            device: The device whose start was pressed.

        """
        self.pause()

    @override
    def _device_left(self, *, device: DeviceIdentity) -> None:
        """An unplugged pad takes its kid with it; with nobody left, back to the title.

        Args:
            device: The device that was unplugged.

        """
        super()._device_left(device=device)
        joined_slots = {player.slot_index for player in self.roster.joined_players}
        for slot_index in [slot for slot in self.kids if slot not in joined_slots]:
            self.kids.pop(slot_index).kill()
        if not self.roster.joined_players:
            # Imported here: the title leads, through the card, to the neighborhood
            from zombies_aint_my_neighbors.title import TitleScene

            self.next_scene = TitleScene(options=self.options, roster=self.roster)
