"""Mr. Muncher's maze: a hand-designed layout of walls, corridors, sprockets and a house.

The layout is text, one string per row of tiles (``MAZE_LAYOUT``). It is symmetric left to
right, every corridor is one tile wide, there are no dead ends, and every open tile can be
reached from every other (the member's ``tests/test_mr_muncher_maze_and_actors.py`` checks
all four). The long corridors at the top and bottom are tunnels: leaving one side enters the other.

Positions are in tile units: the centre of the tile in column c, row r is (c, r), so an actor
standing on a tile centre has whole-number coordinates. The maze knows nothing of pixels; the
game scales tiles to the screen (``MazeGeometry``).
"""

from __future__ import annotations

import enum
import math
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

# What each layout character is
WALL = '#'
SPROCKET = '.'
SNACK = 'o'
EMPTY = ' '  # A corridor tile without a sprocket
TUNNEL = 'T'  # A corridor tile at a wrapping tunnel's mouth, where munchers slow down
HOUSE = 'H'  # Inside the munchers' house: only munchers going in or out move here
DOOR = '-'  # The house's door: munchers pass, the player never does
PLAYER_START = 'P'  # The player's start (a corridor tile without a sprocket)

# Tiles the player may stand on
PLAYER_OPEN_TILES = frozenset({SPROCKET, SNACK, EMPTY, TUNNEL, PLAYER_START})

# Wrapping is checked at half a tile past an edge, so an actor wraps between two tile centres
HALF_TILE = 0.5

MAZE_LAYOUT: tuple[str, ...] = (
    '###########################',
    '#o...........#...........o#',
    '#.####.#####.#.#####.####.#',
    '#.####.#####.#.#####.####.#',
    'T.........................T',
    '#.####.##.#######.##.####.#',
    '#......##....#....##......#',
    '#.####.#####.#.#####.####.#',
    '#.#....##         ##....#.#',
    '#.#.##.## ###-### ##.##.#.#',
    '#...##.   #HHHHH#   .##...#',
    '###.##.## #HHHHH# ##.##.###',
    '#......## #HHHHH# ##......#',
    '#.####.## ####### ##.####.#',
    '#.#....##         ##....#.#',
    '#.#.##.#####.#.#####.##.#.#',
    '#...##.......#.......##...#',
    '#.####.#####.#.#####.####.#',
    '#o..##.......P.......##..o#',
    '###.##.##.#######.##.##.###',
    '#......##....#....##......#',
    '#.##########.#.##########.#',
    'T.........................T',
    '###########################',
)


class Direction(enum.Enum):
    """A direction of travel, as its (x, y) step in tiles (y grows downward)."""

    UP = (0, -1)
    LEFT = (-1, 0)
    DOWN = (0, 1)
    RIGHT = (1, 0)

    @property
    def step_x(self: Self) -> int:
        """The x step of one tile in this direction."""
        return self.value[0]

    @property
    def step_y(self: Self) -> int:
        """The y step of one tile in this direction."""
        return self.value[1]

    @property
    def opposite(self: Self) -> Direction:
        """The direction straight back."""
        return Direction((-self.step_x, -self.step_y))


# The order munchers prefer directions in when two are equally good (the arcade's order)
DIRECTION_PREFERENCE: tuple[Direction, ...] = (
    Direction.UP,
    Direction.LEFT,
    Direction.DOWN,
    Direction.RIGHT,
)


class Maze(BaseModel):
    """A maze layout and the questions the game asks of it.

    Attributes:
        layout: One string per row of tiles, all the same width (characters as above).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    layout: tuple[str, ...]

    @model_validator(mode='after')
    def _check_layout(self: Self) -> Self:
        """Refuse a layout whose rows differ in width, or without exactly one player start.

        Returns:
            The maze.

        Raises:
            ValueError: If the layout is not a rectangle or has no single player start.

        """
        widths = {len(row) for row in self.layout}
        if len(widths) != 1:
            message = f'every row of a maze layout must have the same width, got {sorted(widths)}'
            raise ValueError(message)
        player_starts = sum(row.count(PLAYER_START) for row in self.layout)
        if player_starts != 1:
            message = f'a maze layout needs exactly one player start, got {player_starts}'
            raise ValueError(message)
        return self

    @property
    def columns(self: Self) -> int:
        """The maze's width in tiles."""
        return len(self.layout[0])

    @property
    def rows(self: Self) -> int:
        """The maze's height in tiles."""
        return len(self.layout)

    def tile(self: Self, *, column: int, row: int) -> str:
        """Return the layout character of a tile; columns wrap, rows outside are wall.

        Columns wrap so the tunnel row joins its two ends; every other row has walls at both
        edges, where wrapping changes nothing.

        Args:
            column: The tile's column (any integer: it wraps).
            row: The tile's row.

        Returns:
            The tile's character.

        """
        if not 0 <= row < self.rows:
            return WALL
        return self.layout[row][column % self.columns]

    def is_open_for_player(self: Self, *, column: int, row: int) -> bool:
        """Whether the player may stand on a tile (not a wall, the house or its door).

        Args:
            column: The tile's column.
            row: The tile's row.

        Returns:
            True for a corridor tile.

        """
        return self.tile(column=column, row=row) in PLAYER_OPEN_TILES

    def is_tunnel(self: Self, *, column: int, row: int) -> bool:
        """Whether a tile is part of the wrapping tunnel.

        Args:
            column: The tile's column.
            row: The tile's row.

        Returns:
            True for a tunnel tile.

        """
        return self.tile(column=column, row=row) == TUNNEL

    def cells_holding(self: Self, *, character: str) -> list[tuple[int, int]]:
        """Return every tile holding a layout character, row by row.

        Args:
            character: The character (SPROCKET, SNACK, ...).

        Returns:
            Each tile's (column, row).

        """
        return [
            (column, row)
            for row, row_text in enumerate(self.layout)
            for column, tile in enumerate(row_text)
            if tile == character
        ]

    @property
    def player_start(self: Self) -> tuple[int, int]:
        """The player's start tile (column, row)."""
        ((column, row),) = self.cells_holding(character=PLAYER_START)
        return (column, row)

    @property
    def door(self: Self) -> tuple[int, int]:
        """The house door's tile (column, row)."""
        ((column, row),) = self.cells_holding(character=DOOR)
        return (column, row)

    @property
    def house_entrance(self: Self) -> tuple[int, int]:
        """The corridor tile just above the door, where munchers leave and enter the house."""
        door_column, door_row = self.door
        return (door_column, door_row - 1)

    @property
    def house_centre(self: Self) -> tuple[int, int]:
        """The house tile two below the door: the middle of its three rows."""
        door_column, door_row = self.door
        return (door_column, door_row + 2)

    def wrap_x(self: Self, x: float) -> float:
        """Wrap an x position (in tiles) that went more than half a tile past either edge.

        Args:
            x: The position.

        Returns:
            The same place inside the maze's width.

        """
        if x < -HALF_TILE:
            return x + self.columns
        if x >= self.columns - HALF_TILE:
            return x - self.columns
        return x

    def tile_distance(
        self: Self, *, first: tuple[float, float], second: tuple[float, float]
    ) -> float:
        """Return the straight-line distance between two positions, the short way round.

        Two positions near opposite ends of the tunnel are close: the distance across the wrap
        counts.

        Args:
            first: One position, in tiles.
            second: The other position, in tiles.

        Returns:
            The distance, in tiles.

        """
        across = abs(first[0] - second[0])
        across = min(across, self.columns - across)
        return math.hypot(across, first[1] - second[1])


def build_maze() -> Maze:
    """Return Mr. Muncher's maze.

    Returns:
        The maze of MAZE_LAYOUT.

    """
    return Maze(layout=MAZE_LAYOUT)
