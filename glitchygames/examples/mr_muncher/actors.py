"""Mr. Muncher's actors: the player and the four munchers, moving tile to tile through the maze.

Both move along corridors only: their position (``tile_x``, ``tile_y``) is in tile units, and
they choose a new direction only on a tile's centre, where both coordinates are whole numbers.
Each frame's distance is walked centre to centre (``MazeActor.advance``), so a long frame never
skips a turn.

The player turns where the player asks, as soon as the maze allows: a direction pressed early is
remembered (``wanted_direction``) and taken at the first tile centre where that way is open, and
reversing is immediate, even between centres.

Munchers never reverse on their own. At each tile centre a muncher takes the open direction
whose next tile is closest (in a straight line) to its target tile, preferring up, left, down,
right on a tie. What the target is depends on the mode (scatter: the muncher's home corner;
chase: its personality, ``chase_target``) and on its state: a frightened muncher turns at
random (drawn from the engine's seeded stream, so replays are exact), and an eaten one's eyes
head for the house. A change of mode turns every roaming muncher round (``reverse_soon``).

The actors are world-space sprites (glitchygames/world.py): they keep their positions in tile
units and report ``world_x``/``world_y`` in pixels, and the engine places their rects.
"""

from __future__ import annotations

import enum
import math
from typing import TYPE_CHECKING, Any, Self

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.examples.mr_muncher import drawing
from glitchygames.examples.mr_muncher.maze import DIRECTION_PREFERENCE, Direction, Maze
from glitchygames.randomness import random_stream
from glitchygames.sprites import Sprite
from glitchygames.world import CoordinateSpace

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.examples.mr_muncher.levels import LevelSettings

# The munchers' random stream (glitchygames/randomness.py): frightened munchers' turns
MUNCHER_RANDOM_STREAM = 'mr_muncher.munchers'

# An actor's picture is this many tiles wide (actors overlap the drawn walls a little, as the
# corridors are drawn wider than their tiles)
ACTOR_SIZE_TILES = 1.4
# The player's mouth opens and shuts once for every this many tiles travelled, in this many
# steps (each step a cached picture)
CHOMP_CYCLE_TILES = 1.0
CHOMP_STEPS = 4
# The skirt of a muncher swaps its points every this many seconds of game time
SKIRT_WAVE_SECONDS = 0.15
# The dying player's picture changes in this many steps
DYING_STEPS = 24

# How far ahead of the player the ambusher aims, and the flanker's pivot, in tiles
AMBUSH_TILES_AHEAD = 4
FLANK_PIVOT_TILES_AHEAD = 2
# The shy muncher chases only while farther than this from the player (in tiles); nearer, it
# heads for its corner
SHY_DISTANCE_TILES = 8.0
# Waiting munchers bob this far above and below their seat in the house (in tiles)
HOUSE_BOB_TILES = 0.35


class MazeGeometry(BaseModel):
    """Where the maze sits on screen and how big its tiles are.

    Attributes:
        tile_size: A tile's side, in pixels.
        left: The x of the maze's left edge, in pixels.
        top: The y of the maze's top edge, in pixels.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    tile_size: int
    left: int
    top: int

    def pixel_centre(self: Self, *, tile_x: float, tile_y: float) -> tuple[float, float]:
        """Return the pixel position of a point given in tiles (a tile's centre for whole numbers).

        Args:
            tile_x: The point's x, in tiles.
            tile_y: The point's y, in tiles.

        Returns:
            The (x, y) in pixels.

        """
        return (
            self.left + (tile_x + 0.5) * self.tile_size,
            self.top + (tile_y + 0.5) * self.tile_size,
        )


def nearest_cell(*, tile_x: float, tile_y: float, maze: Maze) -> tuple[int, int]:
    """Return the tile whose centre is nearest a position (halves round up), column wrapped.

    Args:
        tile_x: The position's x, in tiles.
        tile_y: The position's y, in tiles.
        maze: The maze (for its width).

    Returns:
        The tile's (column, row).

    """
    return (math.floor(tile_x + 0.5) % maze.columns, math.floor(tile_y + 0.5))


class MazeActor(Sprite):
    """Something that moves tile to tile through the maze: the player or a muncher."""

    # A world sprite: the engine places its rect from world_x/world_y (glitchygames/world.py)
    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self: Self,
        *,
        maze: Maze,
        geometry: MazeGeometry,
        start: tuple[float, float],
        layer: int,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Place the actor, standing still on its start (named after its class).

        Args:
            maze: The maze it moves through.
            geometry: Where the maze is on screen.
            start: Its start, in tiles.
            layer: The sprite layer it draws on.
            groups: The sprite group to add it to.

        """
        self._layer = layer
        self.picture_size = round(geometry.tile_size * ACTOR_SIZE_TILES)
        super().__init__(
            x=0,
            y=0,
            width=self.picture_size,
            height=self.picture_size,
            name=type(self).__name__,
            groups=groups,
        )
        self.image = pygame.Surface((self.picture_size, self.picture_size), pygame.SRCALPHA)
        self.maze = maze
        self.geometry = geometry
        self.start = start
        self.tile_x, self.tile_y = float(start[0]), float(start[1])
        # The direction it is moving in, or None when standing still
        self.direction: Direction | None = None
        # Hidden actors are not drawn (the engine owns a world sprite's visible: World Space)
        self.hidden = False
        self.dirty = 2

    @property
    def world_x(self: Self) -> float:
        """The x of the picture's top-left corner, in pixels."""
        centre_x, _ = self.geometry.pixel_centre(tile_x=self.tile_x, tile_y=self.tile_y)
        return centre_x - self.picture_size / 2

    @property
    def world_y(self: Self) -> float:
        """The y of the picture's top-left corner, in pixels."""
        _, centre_y = self.geometry.pixel_centre(tile_x=self.tile_x, tile_y=self.tile_y)
        return centre_y - self.picture_size / 2

    @property
    def position(self: Self) -> tuple[float, float]:
        """Its position, in tiles."""
        return (self.tile_x, self.tile_y)

    @property
    def cell(self: Self) -> tuple[int, int]:
        """The tile whose centre is nearest it."""
        return nearest_cell(tile_x=self.tile_x, tile_y=self.tile_y, maze=self.maze)

    @property
    def is_at_tile_centre(self: Self) -> bool:
        """Whether it stands exactly on a tile's centre (where it may turn)."""
        return self.tile_x.is_integer() and self.tile_y.is_integer()

    def place_at(self: Self, *, position: tuple[float, float]) -> None:
        """Put it somewhere, standing still.

        Args:
            position: Where, in tiles.

        """
        self.tile_x, self.tile_y = float(position[0]), float(position[1])
        self.direction = None

    def next_cell_ahead(self: Self) -> tuple[int, int]:
        """Return the tile centre it reaches next: its own on a centre or standing still.

        Returns:
            The tile's (column, row).

        """
        if self.direction is None or self.is_at_tile_centre:
            return self.cell
        if self.direction.step_x:
            column = (
                math.floor(self.tile_x) + 1
                if self.direction.step_x > 0
                else math.ceil(self.tile_x) - 1
            )
            return (column % self.maze.columns, round(self.tile_y))
        row = (
            math.floor(self.tile_y) + 1 if self.direction.step_y > 0 else math.ceil(self.tile_y) - 1
        )
        return (round(self.tile_x) % self.maze.columns, row)

    def _distance_to_next_centre(self: Self, direction: Direction) -> float:
        """Return how far it is, going one way, to the next tile centre.

        Args:
            direction: The way it goes.

        Returns:
            The distance in tiles (1.0 from a centre).

        """
        coordinate = self.tile_x if direction.step_x else self.tile_y
        step = direction.step_x or direction.step_y
        if step > 0:
            return math.floor(coordinate) + 1 - coordinate
        return coordinate - (math.ceil(coordinate) - 1)

    def advance(
        self: Self, *, distance: float, choose_direction: Callable[[], Direction | None]
    ) -> float:
        """Walk a distance along the corridors, choosing a direction at every tile centre.

        On each centre it reaches (or starts on), ``choose_direction`` decides which way to go
        on, or None to stop there. The walk ends at the distance or at such a stop.

        Args:
            distance: How far to walk, in tiles.
            choose_direction: Called on each tile centre; returns the way on, or None to stop.

        Returns:
            The distance actually walked.

        """
        walked = 0.0
        while walked < distance:
            if self.is_at_tile_centre:
                self.direction = choose_direction()
            if self.direction is None:
                break
            to_centre = self._distance_to_next_centre(self.direction)
            step = min(distance - walked, to_centre)
            if step == to_centre:
                # Land exactly on the centre, so the turn test above sees whole numbers
                if self.direction.step_x:
                    self.tile_x = float(round(self.tile_x + self.direction.step_x * step))
                else:
                    self.tile_y = float(round(self.tile_y + self.direction.step_y * step))
            else:
                self.tile_x += self.direction.step_x * step
                self.tile_y += self.direction.step_y * step
            self.tile_x = self.maze.wrap_x(self.tile_x)
            walked += step
        return walked

    def is_direction_open(self: Self, direction: Direction) -> bool:
        """Whether the tile next to its cell, one way, is a corridor (not wall, house or door).

        Munchers roam the same corridors as the player; they go in and out of the house on a
        fixed path that does not ask.

        Args:
            direction: The way to look.

        Returns:
            True if it may go that way from its cell.

        """
        column, row = self.cell
        return self.maze.is_open_for_player(
            column=column + direction.step_x, row=row + direction.step_y
        )


class Player(MazeActor):
    """Mr. Muncher: the popcorn bucket the player steers."""

    def __init__(
        self: Self,
        *,
        maze: Maze,
        geometry: MazeGeometry,
        layer: int,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Put the player on the maze's start, heading left.

        Args:
            maze: The maze.
            geometry: Where the maze is on screen.
            layer: The sprite layer it draws on.
            groups: The sprite group to add it to.

        """
        super().__init__(
            maze=maze,
            geometry=geometry,
            start=maze.player_start,
            layer=layer,
            groups=groups,
        )
        # The way the player last asked to go: taken at the first tile centre where it is open
        self.wanted_direction: Direction | None = Direction.LEFT
        # The way the mouth faces (kept while standing still)
        self.facing = Direction.LEFT
        # Tiles travelled, for the mouth's chomping
        self.travelled = CHOMP_CYCLE_TILES / 2
        # While dying: 0.0 (caught) to 1.0 (gone); None while alive
        self.dying_progress: float | None = None
        self.reset()

    def reset(self: Self) -> None:
        """Back to the start for a new life, already heading left (as in the arcade).

        A way asked for before play starts is taken at the first junction where it is open;
        until then the player goes left.
        """
        self.place_at(position=self.start)
        self.direction = Direction.LEFT
        self.wanted_direction = Direction.LEFT
        self.facing = Direction.LEFT
        self.travelled = CHOMP_CYCLE_TILES / 2
        self.dying_progress = None
        self.hidden = False
        self.pose()

    def travel(self: Self, *, distance: float) -> None:
        """Move for one step of play: reverse at once if asked, else turn at tile centres.

        Args:
            distance: How far the player can go, in tiles.

        """
        if (
            self.direction is not None
            and self.wanted_direction is self.direction.opposite
            and not self.is_at_tile_centre
        ):
            self.direction = self.wanted_direction
        self.travelled += self.advance(distance=distance, choose_direction=self._choose_direction)
        if self.direction is not None:
            self.facing = self.direction

    def _choose_direction(self: Self) -> Direction | None:
        """Return the way on from a tile centre: the wanted way if open, else straight on.

        Returns:
            The direction, or None to stop (against a wall, with no open wanted way).

        """
        if self.wanted_direction is not None and self.is_direction_open(self.wanted_direction):
            return self.wanted_direction
        if self.direction is not None and self.is_direction_open(self.direction):
            return self.direction
        return None

    def pose(self: Self) -> None:
        """Draw the player's picture for this moment: chomping, standing, or dying."""
        if self.dying_progress is not None:
            step = min(DYING_STEPS, math.floor(self.dying_progress * DYING_STEPS))
            self.image = drawing.player_dying_picture(
                size=self.picture_size, progress=step / DYING_STEPS
            )
            return
        cycle = (self.travelled % CHOMP_CYCLE_TILES) / CHOMP_CYCLE_TILES
        # A triangle wave: shut at the cycle's start, wide open half way, shut again
        opening = 1.0 - abs(2.0 * cycle - 1.0)
        mouth_step = min(CHOMP_STEPS - 1, math.floor(opening * CHOMP_STEPS))
        self.image = drawing.player_picture(
            size=self.picture_size,
            looking=self.facing,
            mouth_fraction=mouth_step / (CHOMP_STEPS - 1),
        )


class Personality(enum.Enum):
    """How a muncher picks its chase target."""

    CHASER = 'chaser'  # Straight at the player
    AMBUSHER = 'ambusher'  # At the tiles in front of the player
    FLANKER = 'flanker'  # Opposite the chaser, past a point in front of the player
    SHY = 'shy'  # At the player from afar, but back to its corner when close


class MuncherState(enum.Enum):
    """Where a muncher is in its life."""

    WAITING = 'waiting'  # In the house, bobbing, until released
    LEAVING = 'leaving'  # Walking out through the door
    ROAMING = 'roaming'  # In the maze: scattering, chasing or frightened
    EATEN = 'eaten'  # Only its eyes, heading home
    ENTERING = 'entering'  # Its eyes going down into the house, to come back to life


class MuncherProfile(BaseModel):
    """Who a muncher is: name, look, personality, corner, and seat in the house.

    Attributes:
        name: Its name.
        color: Its body colour.
        personality: How it chases.
        corner: Its scatter target, a tile outside the maze near its corner.
        seat: Where it waits in the house (or starts, for the one outside), in tiles.
        starts_outside: True for the one that starts above the door, roaming at once.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    color: tuple[int, int, int]
    personality: Personality
    corner: tuple[int, int]
    seat: tuple[int, int]
    starts_outside: bool = False


def muncher_profiles(*, maze: Maze) -> tuple[MuncherProfile, ...]:
    """Return the four munchers, the chaser first (the flanker aims off the chaser).

    Args:
        maze: The maze (its size and house decide corners and seats).

    Returns:
        The profiles: Chomper (purple), Snapper (green), Gnasher (orange) and Nibbles
        (magenta).

    """
    centre_column, centre_row = maze.house_centre
    return (
        MuncherProfile(
            name='Chomper',
            color=(165, 95, 255),
            personality=Personality.CHASER,
            corner=(maze.columns - 3, -3),
            seat=maze.house_entrance,
            starts_outside=True,
        ),
        MuncherProfile(
            name='Snapper',
            color=(70, 210, 100),
            personality=Personality.AMBUSHER,
            corner=(2, -3),
            seat=(centre_column, centre_row),
        ),
        MuncherProfile(
            name='Gnasher',
            color=(255, 150, 40),
            personality=Personality.FLANKER,
            corner=(maze.columns - 1, maze.rows),
            seat=(centre_column - 2, centre_row),
        ),
        MuncherProfile(
            name='Nibbles',
            color=(240, 70, 190),
            personality=Personality.SHY,
            corner=(0, maze.rows),
            seat=(centre_column + 2, centre_row),
        ),
    )


class ChaseSituation(BaseModel):
    """What the munchers know of the game when they choose a turn.

    Attributes:
        player_cell: The player's tile.
        player_facing: The way the player faces.
        chaser_cell: The chaser's tile (the flanker aims off it).
        chasing: True while the munchers chase, False while they scatter.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    player_cell: tuple[int, int]
    player_facing: Direction
    chaser_cell: tuple[int, int]
    chasing: bool


def chase_target(
    *,
    personality: Personality,
    situation: ChaseSituation,
    own_cell: tuple[int, int],
    corner: tuple[int, int],
) -> tuple[int, int]:
    """Return the tile a muncher heads for while chasing.

    Args:
        personality: How it chases.
        situation: Where the player and the chaser are.
        own_cell: The muncher's own tile (the shy one keeps its distance).
        corner: Its scatter corner (where the shy one goes when close).

    Returns:
        The target tile (it may lie outside the maze).

    """
    player_column, player_row = situation.player_cell
    facing = situation.player_facing
    if personality is Personality.CHASER:
        return situation.player_cell
    if personality is Personality.AMBUSHER:
        return (
            player_column + facing.step_x * AMBUSH_TILES_AHEAD,
            player_row + facing.step_y * AMBUSH_TILES_AHEAD,
        )
    if personality is Personality.FLANKER:
        pivot_column = player_column + facing.step_x * FLANK_PIVOT_TILES_AHEAD
        pivot_row = player_row + facing.step_y * FLANK_PIVOT_TILES_AHEAD
        chaser_column, chaser_row = situation.chaser_cell
        return (2 * pivot_column - chaser_column, 2 * pivot_row - chaser_row)
    # The shy one
    distance = math.hypot(own_cell[0] - player_column, own_cell[1] - player_row)
    return situation.player_cell if distance > SHY_DISTANCE_TILES else corner


class Muncher(MazeActor):
    """One of the four munchers."""

    def __init__(
        self: Self,
        *,
        profile: MuncherProfile,
        maze: Maze,
        geometry: MazeGeometry,
        layer: int,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Seat the muncher (or stand it above the door).

        Args:
            profile: Who it is.
            maze: The maze.
            geometry: Where the maze is on screen.
            layer: The sprite layer it draws on.
            groups: The sprite group to add it to.

        """
        super().__init__(
            maze=maze,
            geometry=geometry,
            start=profile.seat,
            layer=layer,
            groups=groups,
        )
        self.name = profile.name
        self.profile = profile
        self.state = MuncherState.WAITING
        self.frightened = False
        # Turn round at the next chance (a mode change, or a fright starting)
        self.reverse_soon = False
        # Where it looks while not moving the maze's way (bobbing in the house)
        self.looking = Direction.LEFT
        # The tile it last aimed for (shown by the debug overlay)
        self.target: tuple[int, int] | None = None
        self.reset()

    def reset(self: Self) -> None:
        """Back to its seat (a new life): waiting, or roaming above the door."""
        self.place_at(position=self.profile.seat)
        self.frightened = False
        self.reverse_soon = False
        self.target = None
        self.hidden = False
        if self.profile.starts_outside:
            self.state = MuncherState.ROAMING
            self.direction = Direction.LEFT
            self.looking = Direction.LEFT
        else:
            self.state = MuncherState.WAITING
            self.direction = Direction.UP
            self.looking = Direction.UP

    @property
    def can_touch_player(self: Self) -> bool:
        """Whether touching the player counts: it is in the maze (or walking out), not eyes."""
        return self.state in {MuncherState.ROAMING, MuncherState.LEAVING}

    def speed(self: Self, *, settings: LevelSettings, hurrying: bool) -> float:
        """Return how fast it moves now, in tiles per second.

        Args:
            settings: The level's settings.
            hurrying: True when the chaser hurries (few sprockets left).

        Returns:
            The speed.

        """
        if self.state in {MuncherState.EATEN, MuncherState.ENTERING}:
            return settings.eyes_speed
        if self.state in {MuncherState.WAITING, MuncherState.LEAVING}:
            return settings.house_speed
        column, row = self.cell
        if self.maze.is_tunnel(column=column, row=row):
            return settings.tunnel_speed
        if self.frightened:
            return settings.frightened_speed
        if hurrying and self.profile.personality is Personality.CHASER:
            return settings.hurry_speed
        return settings.muncher_speed

    def travel(self: Self, *, distance: float, situation: ChaseSituation) -> None:
        """Move for one step of play, as its state says.

        Args:
            distance: How far it can go, in tiles.
            situation: What it knows of the player and the mode.

        """
        if self.state is MuncherState.WAITING:
            self._bob(distance=distance)
        elif self.state is MuncherState.LEAVING:
            self._walk_out(distance=distance)
        elif self.state is MuncherState.ENTERING:
            self._walk_in(distance=distance)
        else:  # Roaming, or eyes going home: through the corridors
            if self.reverse_soon and self.direction is not None:
                self.direction = self.direction.opposite
            self.reverse_soon = False
            self.advance(
                distance=distance,
                choose_direction=lambda: self._choose_direction(situation=situation),
            )
            if self.state is MuncherState.EATEN and self.position == self.maze.house_entrance:
                self._arrive_home()
        if self.direction is not None:
            self.looking = self.direction

    def _bob(self: Self, *, distance: float) -> None:
        """Bob up and down on its seat while waiting.

        Args:
            distance: How far it moves, in tiles.

        """
        seat_row = self.profile.seat[1]
        step_y = Direction.UP.step_y if self.direction is Direction.UP else Direction.DOWN.step_y
        self.tile_y += step_y * distance
        if self.tile_y <= seat_row - HOUSE_BOB_TILES:
            self.tile_y = seat_row - HOUSE_BOB_TILES
            self.direction = Direction.DOWN
        elif self.tile_y >= seat_row + HOUSE_BOB_TILES:
            self.tile_y = seat_row + HOUSE_BOB_TILES
            self.direction = Direction.UP

    def _walk_towards(self: Self, *, goal: tuple[int, int], distance: float) -> float:
        """Walk straight towards a point, across first, then up or down (the house's paths).

        Args:
            goal: Where to, in tiles.
            distance: How far it may walk.

        Returns:
            The distance left over after reaching the goal (0.0 if it did not).

        """
        goal_x, goal_y = float(goal[0]), float(goal[1])
        if self.tile_x != goal_x:
            self.direction = Direction.RIGHT if goal_x > self.tile_x else Direction.LEFT
            gap = abs(goal_x - self.tile_x)
            if distance < gap:
                self.tile_x += self.direction.step_x * distance
                return 0.0
            self.tile_x = goal_x
            distance -= gap
        if self.tile_y != goal_y:
            self.direction = Direction.DOWN if goal_y > self.tile_y else Direction.UP
            gap = abs(goal_y - self.tile_y)
            if distance < gap:
                self.tile_y += self.direction.step_y * distance
                return 0.0
            self.tile_y = goal_y
            distance -= gap
        return distance

    def _walk_out(self: Self, *, distance: float) -> None:
        """Walk to the door's column, then up through it into the maze, then roam.

        Args:
            distance: How far it can go, in tiles.

        """
        self._walk_towards(goal=self.maze.house_entrance, distance=distance)
        if self.position == self.maze.house_entrance:
            self.state = MuncherState.ROAMING
            # Facing up, so its first turn may go either way along the corridor; it turns on
            # its next step (any distance left over this step is dropped)
            self.direction = Direction.UP

    def _arrive_home(self: Self) -> None:
        """The eyes reached the door: they go down into the house."""
        self.state = MuncherState.ENTERING
        self.direction = Direction.DOWN

    def _walk_in(self: Self, *, distance: float) -> None:
        """Walk the eyes down into the house; there it comes back to life and walks out.

        Args:
            distance: How far it can go, in tiles.

        """
        self._walk_towards(goal=self.maze.house_centre, distance=distance)
        if self.position == self.maze.house_centre:
            self.state = MuncherState.LEAVING
            self.frightened = False

    def _choose_direction(self: Self, *, situation: ChaseSituation) -> Direction | None:
        """Return the way on from a tile centre: never back, towards its target or at random.

        Args:
            situation: What it knows of the player and the mode.

        Returns:
            The direction (straight back only at a dead end), or None for eyes at the door.

        """
        if self.state is MuncherState.EATEN and self.position == self.maze.house_entrance:
            return None
        backwards = self.direction.opposite if self.direction is not None else None
        options = [
            direction
            for direction in DIRECTION_PREFERENCE
            if direction is not backwards and self.is_direction_open(direction)
        ]
        if not options:
            # A dead end (Mr. Muncher's maze has none): the only way on is back
            return backwards
        if self.frightened and self.state is MuncherState.ROAMING:
            self.target = None
            return random_stream(MUNCHER_RANDOM_STREAM).choice(options)
        target = self._target(situation=situation)
        self.target = target
        column, row = self.cell
        return min(
            options,
            key=lambda direction: self.maze.tile_distance(
                first=(column + direction.step_x, row + direction.step_y), second=target
            ),
        )

    def _target(self: Self, *, situation: ChaseSituation) -> tuple[int, int]:
        """Return the tile it heads for: home when eaten, its corner when scattering, else its prey.

        Args:
            situation: What it knows of the player and the mode.

        Returns:
            The target tile.

        """
        if self.state is MuncherState.EATEN:
            return self.maze.house_entrance
        if not situation.chasing:
            return self.profile.corner
        return chase_target(
            personality=self.profile.personality,
            situation=situation,
            own_cell=self.cell,
            corner=self.profile.corner,
        )

    def pose(self: Self, *, game_time: float, flashing: bool) -> None:
        """Draw the muncher's picture for this moment.

        Args:
            game_time: The scene's game time (the skirt's wave).
            flashing: True while frightened munchers show white (about to recover).

        """
        wave = math.floor(game_time / SKIRT_WAVE_SECONDS) % 2
        if self.state in {MuncherState.EATEN, MuncherState.ENTERING}:
            self.image = drawing.eyes_picture(
                size=self.picture_size, color=self.profile.color, looking=self.looking
            )
        elif self.frightened:
            self.image = drawing.frightened_muncher_picture(
                size=self.picture_size, flashing=flashing, wave=wave
            )
        else:
            self.image = drawing.muncher_picture(
                size=self.picture_size,
                color=self.profile.color,
                looking=self.looking,
                wave=wave,
            )
