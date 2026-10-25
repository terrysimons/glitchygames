"""A simple Mr. Muncher player: it eats sprockets, keeps away from munchers and hunts blue ones.

The golden replay's input script (scripts/record_golden_traces.py: ``mr_muncher_script``)
steers the player with it, pressing the arrow key it asks for, and the tests use it to play
whole levels. It reads the scene (as a person reads the screen) and never changes it.

Each frame it decides at the tile the player reaches next (``MazeActor.next_cell_ahead``).
For each way on from there it works out the player's territory: the corridor tiles the player
would reach at least ``SAFETY_MARGIN_TILES`` before any dangerous muncher could. A way whose
territory is smaller than ``SMALL_TERRITORY_TILES`` is a trap and is taken only when every way
is (then the biggest wins). Among the others it takes the shortest path, through its
territory, to the most wanted goal: a frightened muncher it can catch in time, the bonus, a
snack when a muncher is close, a sprocket. Asked to (``seek_capture_after_seconds``), it
walks into a muncher once, so a recording loses a life.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict

from mr_muncher.game import Phase
from mr_muncher.maze import DIRECTION_PREFERENCE, Direction, Maze

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from mr_muncher.game import MrMuncherScene

type Cell = tuple[int, int]

# A tile is the player's when it gets there at least this many tiles before any muncher could
SAFETY_MARGIN_TILES = 2
# A way on whose territory is smaller than this many tiles is a trap
SMALL_TERRITORY_TILES = 16
# A snack is worth a detour when a muncher is this close to the player (in tiles)
SNACK_DANGER_TILES = 7
# Among traps, turning back counts its territory at this fraction
BACKWARDS_TRAP_DISCOUNT = 0.5
# It chases a frightened muncher only if it can get there with this many seconds of fright left
PREY_SPARE_SECONDS = 0.75
# A key pressed now changes the player's way this long later (the event is handled after this
# frame's logic and read by the next frame's), so it decides that far ahead, as a person would
INPUT_DELAY_SECONDS = 2.0 / 60.0


def _neighbours(*, maze: Maze, cell: Cell) -> Iterable[tuple[Direction, Cell]]:
    """Yield the corridor tiles next to a tile, with the direction to each (tunnel wrapped).

    Args:
        maze: The maze.
        cell: The tile.

    Yields:
        (direction, neighbouring tile) for each open neighbour.

    """
    column, row = cell
    for direction in DIRECTION_PREFERENCE:
        neighbour_column = (column + direction.step_x) % maze.columns
        neighbour_row = row + direction.step_y
        if maze.is_open_for_player(column=neighbour_column, row=neighbour_row):
            yield direction, (neighbour_column, neighbour_row)


def corridor_distances(
    *, maze: Maze, sources: Iterable[Cell], allowed: Collection[Cell] | None = None
) -> dict[Cell, int]:
    """Return every corridor tile's distance (in tiles walked) from the nearest source.

    Args:
        maze: The maze.
        sources: The tiles to measure from.
        allowed: If given, paths only cross these tiles (sources always count).

    Returns:
        Tile -> distance, for every tile reachable from a source.

    """
    distances: dict[Cell, int] = {}
    queue: deque[Cell] = deque()
    for source in sources:
        if source not in distances:
            distances[source] = 0
            queue.append(source)
    while queue:
        cell = queue.popleft()
        for _, neighbour in _neighbours(maze=maze, cell=cell):
            if neighbour not in distances and (allowed is None or neighbour in allowed):
                distances[neighbour] = distances[cell] + 1
                queue.append(neighbour)
    return distances


class WayOn(BaseModel):
    """One way the player could go from its next tile.

    Attributes:
        direction: The way.
        reach: Tiles walked to every tile, going this way (munchers ignored).
        territory: Tiles walked to each tile the player reaches safely going this way, by
            paths that stay safe.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    direction: Direction
    reach: dict[Cell, int]
    territory: dict[Cell, int]


class Autopilot:
    """Chooses the way for Mr. Muncher to go, frame by frame."""

    def __init__(self: Self, *, seek_capture_after_seconds: float | None = None) -> None:
        """Make an autopilot that plays well, or that walks into a muncher once.

        Args:
            seek_capture_after_seconds: After this much game time of a scene, head for the
                nearest dangerous muncher until one catches the player (once); None never.

        """
        self.seek_capture_after_seconds = seek_capture_after_seconds
        self.has_been_caught = False

    def choose_direction(self: Self, *, scene: MrMuncherScene) -> Direction | None:
        """Return the way the player should go, or None to leave it be.

        Args:
            scene: The game.

        Returns:
            The direction to ask for (None only on a tile with no way on).

        """
        maze = scene.maze
        start, arriving = decision_point(scene=scene)
        dangerous = [
            muncher.next_cell_ahead()
            for muncher in scene.munchers
            if muncher.can_touch_player and not muncher.frightened
        ]
        danger = corridor_distances(maze=maze, sources=dangerous)
        ways = [
            way_on(maze=maze, direction=direction, first=neighbour, danger=danger)
            for direction, neighbour in _neighbours(maze=maze, cell=start)
        ]
        if not ways:
            return None
        if self._is_seeking_capture(scene=scene) and dangerous:
            return shortest_way(ways=ways, goals=set(dangerous), safely=False)
        backwards = arriving.opposite if arriving is not None else None
        roomy = [way for way in ways if len(way.territory) >= SMALL_TERRITORY_TILES]
        if not roomy:
            # Every way is a trap: the roomiest, but turning back must be much roomier (turning
            # back and forth between two traps is the surest way to be caught)
            return max(
                ways,
                key=lambda way: (
                    len(way.territory)
                    * (BACKWARDS_TRAP_DISCOUNT if way.direction is backwards else 1.0)
                ),
            ).direction
        # Going on beats turning back: turn back only when no roomy way on leads to anything
        onwards = [way for way in roomy if way.direction is not backwards]
        goals_in_order = goal_sets(scene=scene, start=start, danger=danger)
        for candidates in (onwards, roomy):
            for goals in goals_in_order:
                direction = shortest_way(ways=candidates, goals=goals, safely=True)
                if direction is not None:
                    return direction
        return max(roomy, key=lambda way: len(way.territory)).direction

    def _is_seeking_capture(self: Self, *, scene: MrMuncherScene) -> bool:
        """Whether it is time to walk into a muncher (until the first catch).

        Args:
            scene: The game.

        Returns:
            True while it should seek capture.

        """
        if self.seek_capture_after_seconds is None or self.has_been_caught:
            return False
        if scene.phase is Phase.DYING:
            self.has_been_caught = True
            return False
        return scene.game_time >= self.seek_capture_after_seconds


def decision_point(*, scene: MrMuncherScene) -> tuple[Cell, Direction | None]:
    """Return the tile where a direction asked for now will be taken, and the way in to it.

    That is the next tile centre the player reaches. When it gets there before a key pressed
    now takes effect (INPUT_DELAY_SECONDS), or stands on a centre it is leaving, the way on
    from that centre is already settled (the wanted way if open, else straight on), and the
    decision is at the tile after it.

    Args:
        scene: The game.

    Returns:
        The tile, and the way the player will be going as it arrives (None standing still).

    """
    maze = scene.maze
    player = scene.player
    direction = player.direction
    if direction is None:
        return (player.cell, None)
    column, row = player.next_cell_ahead()
    if player.is_at_tile_centre:
        settled: tuple[Direction | None, ...] = (direction,)
    else:
        gap = abs(player.tile_x - column) + abs(player.tile_y - row)
        gap = min(gap, maze.columns - gap)
        if gap >= scene.settings.player_speed * INPUT_DELAY_SECONDS:
            return ((column, row), direction)
        settled = (player.wanted_direction, direction)
    for way in settled:
        if (
            way is not None
            and way is not direction.opposite
            and maze.is_open_for_player(column=column + way.step_x, row=row + way.step_y)
        ):
            return (((column + way.step_x) % maze.columns, row + way.step_y), way)
    return ((column, row), direction)


def way_on(*, maze: Maze, direction: Direction, first: Cell, danger: dict[Cell, int]) -> WayOn:
    """Work out where the player can get to, and safely, going one way from its next tile.

    Args:
        maze: The maze.
        direction: The way.
        first: The tile that way.
        danger: The dangerous munchers' corridor distances.

    Returns:
        The way, with its reach and territory.

    """
    unreachable = maze.columns * maze.rows
    reach = corridor_distances(maze=maze, sources=[first])
    safe = {
        cell
        for cell, distance in reach.items()
        if distance + 1 + SAFETY_MARGIN_TILES <= danger.get(cell, unreachable)
    }
    territory = (
        corridor_distances(maze=maze, sources=[first], allowed=safe) if first in safe else {}
    )
    return WayOn(direction=direction, reach=reach, territory=territory)


def goal_sets(*, scene: MrMuncherScene, start: Cell, danger: dict[Cell, int]) -> list[set[Cell]]:
    """Return what to head for, most wanted first.

    Args:
        scene: The game.
        start: The player's next tile.
        danger: The dangerous munchers' corridor distances.

    Returns:
        The goal tiles, in order of preference (some may be empty).

    """
    maze = scene.maze
    unreachable = maze.columns * maze.rows
    mine = corridor_distances(maze=maze, sources=[start])
    speed = scene.settings.sugar_rush_speed
    prey = {
        muncher.cell
        for muncher in scene.munchers
        if muncher.can_touch_player
        and muncher.frightened
        and mine.get(muncher.cell, unreachable) / speed
        < scene.frightened_seconds_left - PREY_SPARE_SECONDS
    }
    bonus: set[Cell] = {scene.message_cell} if scene.bonus.visible else set()
    uneaten = [cell for cell, sprocket in scene.sprockets.items() if not sprocket.eaten]
    is_threatened = danger.get(start, unreachable) <= SNACK_DANGER_TILES
    snacks = {cell for cell in uneaten if scene.sprockets[cell].is_snack and is_threatened}
    plain = {cell for cell in uneaten if not scene.sprockets[cell].is_snack}
    return [prey, bonus, snacks, plain, set(uneaten)]


def shortest_way(*, ways: list[WayOn], goals: set[Cell], safely: bool) -> Direction | None:
    """Return the way with the shortest walk to any goal.

    Args:
        ways: The ways to choose from.
        goals: The tiles to reach.
        safely: Walk only through each way's territory (else anywhere it reaches).

    Returns:
        The best way's direction, or None if no way reaches a goal.

    """
    best: tuple[int, Direction] | None = None
    for way in ways:
        distances = way.territory if safely else way.reach
        for goal in goals & distances.keys():
            if best is None or distances[goal] < best[0]:
                best = (distances[goal], way.direction)
    return best[1] if best is not None else None
