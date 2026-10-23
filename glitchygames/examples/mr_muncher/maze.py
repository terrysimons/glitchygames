"""Mr. Muncher's maze: a grid of wall cells, and the sprockets laid out in its open cells.

The maze is a border of walls with a few small L-shaped wall pieces inside, each placed by
chance; the sprockets (the game's dots) are scattered by chance over the open cells away from
the border. Both draw from a ``random.Random`` the caller passes (the game passes the engine's
seeded stream, so a replay builds the same maze).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    import random
    from collections.abc import Iterator

# The side of one grid cell, in pixels
GRID_SIZE = 20

# Inner wall pieces: one is tried every INNER_WALL_ROW_STEP rows from INNER_WALL_FIRST_ROW, and
# every INNER_WALL_COLUMN_STEP columns from INNER_WALL_FIRST_COLUMN, stopping as far from the
# bottom and right edges as the first row and column are from the top and left
INNER_WALL_FIRST_ROW = 5
INNER_WALL_ROW_STEP = 8
INNER_WALL_FIRST_COLUMN = 10
INNER_WALL_COLUMN_STEP = 15
# The chance that each tried inner wall piece is built
INNER_WALL_CHANCE = 0.7

# Sprockets are tried in every open cell at least this many cells from the edge of the grid
SPROCKET_EDGE_MARGIN_CELLS = 2
# The chance that each tried open cell holds a sprocket
SPROCKET_CHANCE = 0.3


class Maze(BaseModel):
    """The maze's wall cells.

    Attributes:
        columns: The grid's width in cells.
        rows: The grid's height in cells.
        walls: ``walls[row][column]`` is True for a wall cell.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    columns: int
    rows: int
    walls: tuple[tuple[bool, ...], ...]

    def is_wall_cell(self: Self, *, column: int, row: int) -> bool:
        """Whether a cell is a wall; every cell outside the grid counts as one.

        Args:
            column: The cell's column.
            row: The cell's row.

        Returns:
            True for a wall cell or a cell outside the grid.

        """
        if 0 <= column < self.columns and 0 <= row < self.rows:
            return self.walls[row][column]
        return True

    def is_wall_at(self: Self, *, x: float, y: float) -> bool:
        """Whether a pixel position lies in a wall cell (or outside the grid).

        Args:
            x: The position's x, in pixels.
            y: The position's y, in pixels.

        Returns:
            True if the position is in a wall cell or outside the grid.

        """
        return self.is_wall_cell(column=int(x // GRID_SIZE), row=int(y // GRID_SIZE))

    def wall_cells(self: Self) -> Iterator[tuple[int, int]]:
        """Yield every wall cell, row by row.

        Yields:
            Each wall cell's (column, row).

        """
        for row, row_walls in enumerate(self.walls):
            for column, is_wall in enumerate(row_walls):
                if is_wall:
                    yield (column, row)


def build_maze(*, columns: int, rows: int, random_generator: random.Random) -> Maze:
    """Build a maze: walls all round the border, and some L-shaped pieces inside.

    Each inner piece is three cells: its corner, the cell to the corner's right and the cell
    below the corner.

    Args:
        columns: The grid's width in cells.
        rows: The grid's height in cells.
        random_generator: Decides which inner pieces are built.

    Returns:
        The maze.

    """
    walls = [[False] * columns for _ in range(rows)]
    for column in range(columns):
        walls[0][column] = True
        walls[rows - 1][column] = True
    for row in range(rows):
        walls[row][0] = True
        walls[row][columns - 1] = True

    for row in range(INNER_WALL_FIRST_ROW, rows - INNER_WALL_FIRST_ROW, INNER_WALL_ROW_STEP):
        for column in range(
            INNER_WALL_FIRST_COLUMN, columns - INNER_WALL_FIRST_COLUMN, INNER_WALL_COLUMN_STEP
        ):
            if random_generator.random() < INNER_WALL_CHANCE:
                # The ranges stop well inside the border, so both neighbours are in the grid
                walls[row][column] = True
                walls[row][column + 1] = True
                walls[row + 1][column] = True

    return Maze(columns=columns, rows=rows, walls=tuple(tuple(row_walls) for row_walls in walls))


def sprocket_centres(*, maze: Maze, random_generator: random.Random) -> list[tuple[int, int]]:
    """Scatter sprockets over the maze's open cells, away from its edges.

    Args:
        maze: The maze.
        random_generator: Decides which open cells hold a sprocket.

    Returns:
        Each sprocket's centre in pixels (the centre of its cell), row by row.

    """
    return [
        (column * GRID_SIZE + GRID_SIZE // 2, row * GRID_SIZE + GRID_SIZE // 2)
        for row in range(SPROCKET_EDGE_MARGIN_CELLS, maze.rows - SPROCKET_EDGE_MARGIN_CELLS)
        for column in range(SPROCKET_EDGE_MARGIN_CELLS, maze.columns - SPROCKET_EDGE_MARGIN_CELLS)
        # The chance is drawn for open cells only
        if not maze.is_wall_cell(column=column, row=row)
        and random_generator.random() < SPROCKET_CHANCE
    ]
