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
no sprite file loads mid-game: a zombie's load took 27 to 41 ms. Idle ones wait hidden in the
scene's group (never removed: a removed sprite must not be held, tests/replay/
test_removed_sprites_are_freed.py); a spawn or a shot takes one and shows it, and one that has
gone hides and is given back.

Feature plan 7 (plans/2026-11-15-zombies-aint-my-neighbors-7-neighbors-and-lives.md): the run
(``run_state.RunState``: the stage, its neighbors, each player's lives) arrives with the scene.
Its neighbors stand at places drawn from ``zombies_aint_my_neighbors.neighbor-places``; a kid's
touch saves one, a zombie's loses one (kids are checked first, so a tie is a save), and zombies
chase the nearest kid or neighbor. A knockout costs a life; on the last, the kid is out for the
stage (the camera and the group's span leave it out). When every neighbor has gone and at least
one was saved, the exit door opens; a kid through it clears the stage, everyone still in cheers
for ``CHEER_SECONDS`` while the yard stands still, and the card brings the next stage with only
the neighbors saved. Nobody saved, or every player out, is the game over.

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
from zombies_aint_my_neighbors.exit_door import DOOR_SIZE, ExitDoor
from zombies_aint_my_neighbors.game_over import GameOverScene
from zombies_aint_my_neighbors.hud import Hud
from zombies_aint_my_neighbors.kid import (
    FIRE_SECONDS,
    KID_HEIGHT,
    KID_WIDTH,
    TIME_TOLERANCE,
    Kid,
    KidState,
    MirrorCache,
)
from zombies_aint_my_neighbors.neighbor import Neighbor, neighbor_places, touching
from zombies_aint_my_neighbors.pool import SpritePool
from zombies_aint_my_neighbors.roster import JoinRoster
from zombies_aint_my_neighbors.roster_scene import (
    KEYBOARD_IDENTITY,
    RosterScene,
    gamepad_identity,
)
from zombies_aint_my_neighbors.run_state import NeighborKind, RunState, as_run
from zombies_aint_my_neighbors.tv import TV_SIZE, ZOMBIES_IN_ALL, Tv, TvHit, may_spawn
from zombies_aint_my_neighbors.zap import (
    FIZZLE_SECONDS,
    ZAP_RANGE_SECONDS,
    ZAP_SIZE,
    Zap,
    ZapState,
    first_struck,
)
from zombies_aint_my_neighbors.zombie import Zombie, touches

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glitchygames.events.base import ControllerButtonEvent, JoyButtonEvent, KeyEvent
    from glitchygames.input.action_map import ActionMap
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
# Feature plan 7: the stream the neighbors' places come from, the exit door in the top hedge's
# middle, and how long the kids cheer a cleared stage
NEIGHBOR_PLACES_STREAM: Final = 'zombies_aint_my_neighbors.neighbor-places'
EXIT_DOOR_PLACE: Final = (YARD_WIDTH / 2 - DOOR_SIZE / 2, 0.0)
CHEER_SECONDS: Final = 1.5
# Feature plan 8: K, or a pad's Y (Y's number on the joystick layer too), switches the weapon
SWITCH_ACTION: Final = 'switch_weapon'
SWITCH_SCANCODE: Final = pygame.KSCAN_K
SWITCH_BUTTON: Final = pygame.CONTROLLER_BUTTON_Y


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
    # After a hitch the yard advances at most this much (as Clockwork Keep's does): a zap's step
    # (320 px/s) stays under 16 px, shorter than its hitbox and a zombie's together, so it never
    # passes through one; a standing shot's pose and a hit's flash stay on screen
    MAX_FRAME_SECONDS = 0.05

    @override
    def __init__(
        self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
        roster: JoinRoster | dict[str, Any] | None = None,
        run: RunState | dict[str, Any] | None = None,
    ) -> None:
        """Make the neighborhood for the joined players (the keyboard as P1 when none are given).

        Args:
            options: The engine's options.
            groups: The sprite groups to draw into (a new LayeredDirty when None).
            roster: The players: a roster, its JSON form (as a replay passes it back), or None
                for the keyboard alone.
            run: The run this stage plays: a run, its JSON form, or None for a new run.

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
        self.yard_bounds = pygame.Rect(0, 0, YARD_WIDTH, YARD_HEIGHT)
        self.kids: dict[int, Kid] = {}
        self._yard_drawn = False
        # The run: as the stage began (for a replay) and as it is now (lives change)
        self.run = as_run(run)
        self._starting_run = self.run
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
        # Built now, before play: every zombie and zap the yard will need
        self.zombie_pool = SpritePool(make=self._make_zombie, size=ZOMBIE_POOL_SIZE)
        self.zap_pool = SpritePool(make=self._make_zap, size=ZAP_POOL_SIZE)
        places = neighbor_places(
            stream=random_stream(NEIGHBOR_PLACES_STREAM), count=len(self.run.neighbors)
        )
        self.neighbors = [
            Neighbor(kind=kind, world_x=float(x), world_y=float(y), groups=self.all_sprites)
            for kind, (x, y) in zip(self.run.neighbors, places, strict=True)
        ]
        for neighbor in self.neighbors:
            neighbor.dt_tick(0.0)
            self._order_by_feet(neighbor)
        # The neighbors rescued this stage, in the order rescued
        self.rescued: list[NeighborKind] = []
        door_x, door_y = EXIT_DOOR_PLACE
        self.exit_door = ExitDoor(world_x=door_x, world_y=door_y, groups=self.all_sprites)
        self.exit_door.dt_tick(0.0)
        self._order_by_feet(self.exit_door, height=DOOR_SIZE)
        # Whether a kid has left through the door, and how long the kids have cheered
        self.stage_cleared = False
        self._cheer_seconds = 0.0
        self.hud = Hud(
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            groups=self.all_sprites,
        )
        self._show_hud()

    def _show_hud(self) -> None:
        """Show the lives, the stage and the neighbors rescued."""
        self.hud.show(
            run=self.run,
            joined_slots={player.slot_index for player in self.roster.joined_players},
            rescued=len(self.rescued),
            total=len(self._starting_run.neighbors),
            kids=self.kids,
        )

    @override
    @staticmethod
    def _create_action_map(*, options: Mapping[str, Any]) -> ActionMap:
        """Bind the screens' controls, and K or a pad's Y to switch weapons (feature plan 8).

        Args:
            options: The engine's options (the map follows its input mode).

        Returns:
            The action map.

        """
        actions = RosterScene._create_action_map(options=options)
        actions.bind(SWITCH_ACTION, scancode=SWITCH_SCANCODE, controller_button=SWITCH_BUTTON)
        return actions

    @override
    def on_key_down_event(self, event: KeyEvent) -> None:
        """K switches the keyboard player's weapon; other keys as every screen's.

        Args:
            event: The key press.

        """
        if self.actions.get_action(event) == SWITCH_ACTION:
            self._switch_weapon(device=KEYBOARD_IDENTITY)
        else:
            super().on_key_down_event(event)

    @override
    def on_controller_button_down_event(self, event: ControllerButtonEvent) -> None:
        """Y on a mapped pad switches that pad's kid's weapon.

        Args:
            event: The button press.

        """
        if self.actions.get_action(event) == SWITCH_ACTION:
            self._switch_weapon(device=gamepad_identity(instance_id=event.instance_id))
        else:
            super().on_controller_button_down_event(event)

    @override
    def on_joy_button_down_event(self, event: JoyButtonEvent) -> None:
        """Y's number on the joystick layer switches that pad's kid's weapon.

        Args:
            event: The button press.

        """
        if self.actions.get_action(event) == SWITCH_ACTION:
            self._switch_weapon(device=gamepad_identity(instance_id=event.instance_id))
        else:
            super().on_joy_button_down_event(event)

    def _switch_weapon(self, *, device: DeviceIdentity) -> None:
        """Switch the weapon of the kid whose player is on a device (nobody's: nothing)."""
        for player in self.roster.joined_players:
            if player.device == device:
                self.kids[player.slot_index].switch_weapon()

    @override
    def replay_arguments(self) -> dict[str, Any]:
        """Rebuild this stage as it began: the roster and the run.

        Returns:
            Both, as JSON reads them back.

        """
        return {**super().replay_arguments(), 'run': self._starting_run.model_dump(mode='json')}

    def _make_zombie(self) -> Zombie:
        """Make a zombie for the pool, waiting hidden in the scene's group.

        Returns:
            The zombie.

        """
        zombie = Zombie(
            world_x=0.0, world_y=0.0, mirror_cache=self.mirror_cache, groups=self.all_sprites
        )
        zombie.put_away()
        return zombie

    def _make_zap(self) -> Zap:
        """Make a zap for the pool, waiting hidden in the scene's group.

        Returns:
            The zap.

        """
        zap = Zap(
            centre=(0.0, 0.0),
            direction=(1.0, 0.0),
            bounds=self.yard_bounds,
            groups=self.all_sprites,
        )
        zap.put_away()
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
            kid.bounds = self.yard_bounds
            # The weapon the slot held when the last stage cleared (the battery starts full)
            kid.weapon = self.run.weapons[player.slot_index]
            self.kids[player.slot_index] = kid
            self._order_by_feet(kid)
            # The laser's dot lies on the lawn: over the yard, under everything standing on it
            self.all_sprites.change_layer(kid.dot, YARD_LAYER + 1)

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
        self.zaps.append(zap)
        self.zap_owners[zap] = slot_index
        self._order_by_feet(zap, height=ZAP_SIZE)
        return zap

    def _order_by_feet(
        self, sprite: Kid | Zombie | Tv | Zap | Neighbor | ExitDoor, *, height: int = KID_HEIGHT
    ) -> None:
        """Draw a sprite in order of its feet: lower on the screen is in front."""
        self.all_sprites.change_layer(sprite, round(sprite.world_y + height))

    def _order_effect(self, neighbor: Neighbor) -> None:
        """Draw a neighbor's rescue or loss a frame's height in front of where it stood.

        Whoever caused it stands on it, feet near the neighbor's; this keeps them from hiding it.
        """
        if neighbor.effect is not None:
            feet_layer = round(neighbor.world_y + KID_HEIGHT)
            self.all_sprites.change_layer(neighbor.effect, feet_layer + KID_HEIGHT)

    def _order_kid(self, kid: Kid) -> None:
        """Draw a kid by its feet, its remote just in front of it (just behind when facing up)."""
        self._order_by_feet(kid)
        kid_layer = self.all_sprites.get_layer_of_sprite(kid)
        hand_layer = kid_layer + (1 if kid.remote_in_front else -1)
        self.all_sprites.change_layer(kid.remote, hand_layer)
        self.all_sprites.change_layer(kid.laser_pointer, hand_layer)

    @override
    def dt_tick(self, dt: float) -> None:
        """Move each kid by its player's input, keep the group together, pose the kids.

        Args:
            dt: The frame's time, in seconds.

        """
        super().dt_tick(dt)
        if self.stage_cleared:
            self._cheer(dt)
            return
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
        self._save_neighbors()
        self._run_tvs(dt)
        self._run_zombies(dt)
        self._run_zaps(dt)
        self._run_neighbors(dt)
        self._end_the_stage_when_done()
        self._show_hud()

    def _save_neighbors(self) -> None:
        """Each standing kid saves each standing neighbor it touches (before zombies move)."""
        for kid in self.kids.values():
            if kid.state is not KidState.ACTIVE:
                continue
            for neighbor in self.neighbors:
                if neighbor.is_standing and touching(kid, neighbor) and neighbor.rescue():
                    self.rescued.append(neighbor.kind)
                    self._order_effect(neighbor)

    def _run_neighbors(self, dt: float) -> None:
        """Let each neighbor see the zombies, pose it, and let go of those whose effect ended."""
        for neighbor in self.neighbors:
            neighbor.notice(zombies=self.zombies)
            neighbor.dt_tick(dt)
        self.neighbors = [neighbor for neighbor in self.neighbors if not neighbor.is_gone]
        self.exit_door.dt_tick(dt)

    def _end_the_stage_when_done(self) -> None:
        """Open the door, clear the stage, or end the game, as the yard now stands."""
        if self.next_scene is not None:
            return
        joined = [self.kids[player.slot_index] for player in self.roster.joined_players]
        if joined and all(kid.state is KidState.OUT for kid in joined):
            self.next_scene = GameOverScene(options=self.options, roster=self.roster)
            return
        if self.neighbors:
            return
        if not self.rescued:
            self.next_scene = GameOverScene(options=self.options, roster=self.roster)
            return
        self.exit_door.open()
        if self.exit_door.is_passable and any(
            kid.state is KidState.ACTIVE and touching(kid, self.exit_door)
            for kid in self.kids.values()
        ):
            self.stage_cleared = True
            for kid in self.kids.values():
                kid.cheer()

    def _run_with_held_weapons(self) -> RunState:
        """Return the run with the weapon each kid holds now (a free slot keeps the run's).

        Returns:
            The run.

        """
        weapons = tuple(
            self.kids[slot_index].weapon if slot_index in self.kids else weapon
            for slot_index, weapon in enumerate(self.run.weapons)
        )
        return self.run.with_weapons(weapons=weapons)

    def _cheer(self, dt: float) -> None:
        """The yard stands still while the kids cheer; then the card brings the next stage."""
        for kid in self.kids.values():
            kid.dt_tick(dt)
        self.exit_door.dt_tick(dt)
        self._cheer_seconds += dt
        if self._cheer_seconds >= CHEER_SECONDS - TIME_TOLERANCE and self.next_scene is None:
            # Imported here: the card leads to the neighborhood
            from zombies_aint_my_neighbors.feature_card import FeatureCardScene

            self.next_scene = FeatureCardScene(
                options=self.options,
                roster=self.roster,
                run=self._run_with_held_weapons().next_stage(rescued=tuple(self.rescued)),
            )

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
            # The lasers shining now (feature plan 8), read for each zombie: a knockout earlier
            # in this frame puts its kid's dot out for the zombies after
            lit_dots = [kid.dot for kid in kids if kid.laser_lit]
            zombie.chase(kids=kids, neighbors=self.neighbors, dots=lit_dots, dt=dt)
            for slot_index, kid in self.kids.items():
                if kid.is_touchable and touches(zombie=zombie, kid=kid):
                    last_life = self.run.lives[slot_index] <= 1
                    if kid.knock_out(last_life=last_life):
                        self.run = self.run.lose_life(slot_index=slot_index)
                    zombie.grab()
            if not zombie.is_dying:
                for neighbor in self.neighbors:
                    if neighbor.is_standing and touching(zombie, neighbor) and neighbor.lose():
                        zombie.grab()
                        self._order_effect(neighbor)
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
            if zap.state is ZapState.GONE:
                # Fizzled out this frame: hidden, waiting for its pool
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
        for zap in [zap for zap in self.zaps if zap.state is ZapState.GONE]:
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
        # A kid gone for the stage (faded out) no longer holds the group together
        others = [
            other
            for other in self.kids.values()
            if other is not kid and other.state is not KidState.OUT
        ]
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
        # The kids not yet gone for the stage (a fading kid still shows); when every one is
        # gone, all of them (the camera stays put)
        kids = [kid for kid in self.kids.values() if kid.state is not KidState.OUT] or list(
            self.kids.values()
        )
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
