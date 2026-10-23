"""Mr. Muncher's pictures, drawn with pygame's primitives: the maze, the actors, sprockets, panels.

The look is a cinema's: velvet walls with gold trim, Mr. Muncher a popcorn bucket with a face,
the munchers spiky fuzzballs, sprockets like a film strip's sprocket holes, snacks golden
sparkles and the bonus a film reel.

Shapes are drawn SUPERSAMPLE times larger and smooth-scaled down, which anti-aliases their
edges. Every function returns a new or cached surface that callers must not draw on: the
results are cached (``functools.cache``) because the game asks for the same few pictures every
frame. Surfaces with per-pixel alpha are used throughout, so drawing one onto the opaque scene
background never leaves transparent pixels behind (glitchygames/opacity.py).
"""

from __future__ import annotations

import functools
import math

import pygame

from glitchygames.examples.mr_muncher.maze import WALL, Direction, Maze

type Color = tuple[int, int, int]

# Shapes are drawn this many times larger, then smooth-scaled down (anti-aliasing)
SUPERSAMPLE = 4
# The maze is drawn this many times larger (its blur is the costly part, so less than shapes)
MAZE_SUPERSAMPLE = 2

# The maze: corridors are black; walls are dark velvet inside a gold trim
CORRIDOR_COLOR: Color = (0, 0, 0)
WALL_FILL_COLOR: Color = (64, 10, 28)
WALL_EDGE_COLOR: Color = (235, 185, 70)
# The level-clear flash: white trim on lighter velvet
WALL_FLASH_EDGE_COLOR: Color = (255, 255, 255)
WALL_FLASH_FILL_COLOR: Color = (130, 30, 60)
DOOR_COLOR: Color = (255, 230, 150)
# Corridors are drawn this fraction of a tile wider on each side than their tiles, so walls
# between two corridors are thinner than a tile and actors look at home in the corridors
CORRIDOR_WIDENING_FRACTION = 0.2
# The blur that rounds every wall corner, as a fraction of a tile
CORNER_ROUNDING_FRACTION = 0.15
# Blurred wall coverage at or above this (of 255) is wall; above WALL_FILL_THRESHOLD, inside
# the trim; the gap between the two thresholds is the trim's thickness
WALL_EDGE_THRESHOLD = 128
WALL_FILL_THRESHOLD = 190
# The door is a bar this fraction of a tile thick, across its tile's middle
DOOR_THICKNESS_FRACTION = 0.2

# Mr. Muncher: a red-and-white striped popcorn bucket, popcorn heaped on top, a face on front
BUCKET_RED: Color = (235, 40, 50)
BUCKET_WHITE: Color = (255, 255, 255)
POPCORN_COLOR: Color = (255, 246, 205)
POPCORN_SHADOW_COLOR: Color = (215, 190, 120)
EYE_WHITE_COLOR: Color = (255, 255, 255)
EYE_OUTLINE_COLOR: Color = (40, 20, 20)
PUPIL_COLOR: Color = (20, 20, 30)
MOUTH_COLOR: Color = (90, 0, 10)
TOOTH_COLOR: Color = (255, 255, 255)
# The bucket's top edge and bottom, and half its width there, as fractions of the picture
BUCKET_TOP_FRACTION = 0.32
BUCKET_BOTTOM_FRACTION = 0.97
BUCKET_TOP_HALF_WIDTH_FRACTION = 0.48
BUCKET_BOTTOM_HALF_WIDTH_FRACTION = 0.36
# The popcorn heaped on top: (x, y, radius) of each puff, as fractions of the picture
POPCORN_PUFFS: tuple[tuple[float, float, float], ...] = (
    (0.24, 0.26, 0.13),
    (0.42, 0.17, 0.15),
    (0.60, 0.19, 0.14),
    (0.77, 0.27, 0.12),
    (0.50, 0.28, 0.12),
)
# The face: eye height and spacing, mouth height and width, as fractions of the picture
FACE_EYE_Y_FRACTION = 0.52
FACE_EYE_SPACING_FRACTION = 0.16
FACE_EYE_RADIUS_FRACTION = 0.1
FACE_MOUTH_Y_FRACTION = 0.78
FACE_MOUTH_WIDTH_FRACTION = 0.4
FACE_MOUTH_SHUT_FRACTION = 0.04
FACE_MOUTH_OPEN_FRACTION = 0.18
# The dying bucket sinks to this fraction of its height while its popcorn bursts out
DYING_SQUASH_FRACTION = 0.25

# Munchers: spiky fuzzballs with angry brows and a jagged grin
FUZZ_SPIKES = 11
FUZZ_INNER_FRACTION = 0.74
BROW_COLOR: Color = (20, 20, 30)
GRIN_COLOR: Color = (20, 0, 10)
FRIGHTENED_COLOR: Color = (90, 100, 190)
FRIGHTENED_FACE_COLOR: Color = (230, 230, 255)
FLASHING_COLOR: Color = (240, 240, 255)
FLASHING_FACE_COLOR: Color = (210, 40, 60)
# An eaten muncher is its eyes inside a faint ring of its colour
EATEN_RING_ALPHA = 110

# Sprockets (the dots to eat) look like a film strip's sprocket holes; snacks are wrapped candies
SPROCKET_COLOR: Color = (255, 214, 170)
SPROCKET_SIZE_FRACTION = 0.25
SNACK_COLOR: Color = (255, 190, 50)
SNACK_CORE_COLOR: Color = (255, 250, 220)
SNACK_WRAPPER_COLOR: Color = (255, 120, 60)
SNACK_SIZE_FRACTION = 0.85
# A snack's dim twinkle is this fraction of its full size
SNACK_DIM_FRACTION = 0.7

# The bonus film reel
REEL_COLOR: Color = (200, 205, 215)
REEL_RIM_COLOR: Color = (120, 125, 140)
REEL_HOLE_COUNT = 5

# The side panels look like the edge of a film strip
FILM_COLOR: Color = (28, 22, 18)
SPROCKET_HOLE_COLOR: Color = (70, 58, 46)
SPROCKET_HOLE_WIDTH = 10
SPROCKET_HOLE_HEIGHT = 8
SPROCKET_HOLE_SPACING = 20
SPROCKET_HOLE_MARGIN = 6


def _smoothed(surface: pygame.Surface, *, size: tuple[int, int]) -> pygame.Surface:
    """Return a supersampled drawing scaled down to its size (anti-aliased).

    Args:
        surface: The drawing at its larger size.
        size: The size to scale it to.

    Returns:
        The scaled drawing.

    """
    return pygame.transform.smoothscale(surface, size)


@functools.cache
def maze_picture(
    *, layout: tuple[str, ...], tile_size: int, flashing: bool = False
) -> pygame.Surface:
    """Draw a maze: black corridors, walls with rounded corners and an edge, the house door.

    Every open tile (the house included) is drawn as a black square widened by
    CORRIDOR_WIDENING_FRACTION of a tile on each side; the rest is wall. The wall shape is then
    blurred and cut at two thresholds: the first gives the wall's outline (rounded at every
    corner), the second the inside of its edge. Cached by layout (a Maze model is not hashable
    to the type checker).

    Args:
        layout: The maze's layout (``Maze.layout``).
        tile_size: A tile's side, in pixels.
        flashing: Draw the level-clear flash colours instead.

    Returns:
        The maze picture, ``maze.columns * tile_size`` by ``maze.rows * tile_size``.

    """
    maze = Maze(layout=layout)
    big_tile = tile_size * MAZE_SUPERSAMPLE
    size = (maze.columns * big_tile, maze.rows * big_tile)
    widening = round(big_tile * CORRIDOR_WIDENING_FRACTION)
    coverage = pygame.Surface(size)
    coverage.fill((255, 255, 255))
    for row in range(maze.rows):
        for column in range(maze.columns):
            if maze.tile(column=column, row=row) != WALL:
                tile_rect = pygame.Rect(column * big_tile, row * big_tile, big_tile, big_tile)
                pygame.draw.rect(coverage, (0, 0, 0), tile_rect.inflate(2 * widening, 2 * widening))
    blurred = pygame.transform.gaussian_blur(
        coverage, max(1, round(big_tile * CORNER_ROUNDING_FRACTION))
    )
    white = (255, 255, 255)

    def coverage_at_least(threshold: int) -> pygame.mask.Mask:
        tolerance = 255 - threshold
        return pygame.mask.from_threshold(blurred, white, (tolerance, tolerance, tolerance, 255))

    edge_color, fill_color = (
        (WALL_FLASH_EDGE_COLOR, WALL_FLASH_FILL_COLOR)
        if flashing
        else (WALL_EDGE_COLOR, WALL_FILL_COLOR)
    )
    picture = pygame.Surface(size, pygame.SRCALPHA)
    picture.fill((*CORRIDOR_COLOR, 255))
    coverage_at_least(WALL_EDGE_THRESHOLD).to_surface(
        picture, setcolor=(*edge_color, 255), unsetcolor=None
    )
    coverage_at_least(WALL_FILL_THRESHOLD).to_surface(
        picture, setcolor=(*fill_color, 255), unsetcolor=None
    )
    door_column, door_row = maze.door
    door_thickness = round(big_tile * DOOR_THICKNESS_FRACTION)
    door_rect = pygame.Rect(
        door_column * big_tile - widening,
        door_row * big_tile + (big_tile - door_thickness) // 2,
        big_tile + 2 * widening,
        door_thickness,
    )
    pygame.draw.rect(picture, (*DOOR_COLOR, 255), door_rect)
    return _smoothed(picture, size=(maze.columns * tile_size, maze.rows * tile_size))


def _draw_bucket(
    *, surface: pygame.Surface, big: int, height_fraction: float, popcorn: bool
) -> None:
    """Draw the popcorn bucket: its stripes, its rim and, optionally, its popcorn.

    It stands on the picture's bottom, squashed to a fraction of its height.

    Args:
        surface: The supersampled picture to draw on.
        big: Its side.
        height_fraction: 1.0 for the whole bucket; less squashes it down.
        popcorn: Heap popcorn on top.

    """
    bottom = big * BUCKET_BOTTOM_FRACTION
    top = bottom - (bottom - big * BUCKET_TOP_FRACTION) * height_fraction
    top_half = big * BUCKET_TOP_HALF_WIDTH_FRACTION
    bottom_half = big * BUCKET_BOTTOM_HALF_WIDTH_FRACTION
    centre_x = big / 2
    if popcorn:
        for puff_x, puff_y, radius in POPCORN_PUFFS:
            puff_centre = (big * puff_x, big * puff_y)
            pygame.draw.circle(
                surface, POPCORN_SHADOW_COLOR, (puff_centre[0], puff_centre[1] + 3), big * radius
            )
            pygame.draw.circle(surface, POPCORN_COLOR, puff_centre, big * radius)

    def edge_x(*, across: float, down: float) -> float:
        half = top_half + (bottom_half - top_half) * down
        return centre_x - half + 2 * half * across

    pygame.draw.polygon(
        surface,
        BUCKET_RED,
        [(centre_x - top_half, top), (centre_x + top_half, top), (centre_x + bottom_half, bottom),
         (centre_x - bottom_half, bottom)],
    )  # fmt: skip
    stripes = 8
    for stripe in range(1, stripes, 4):
        for left_edge in (stripe, stripes - stripe - 1):
            pygame.draw.polygon(
                surface,
                BUCKET_WHITE,
                [
                    (edge_x(across=left_edge / stripes, down=0.0), top),
                    (edge_x(across=(left_edge + 1) / stripes, down=0.0), top),
                    (edge_x(across=(left_edge + 1) / stripes, down=1.0), bottom),
                    (edge_x(across=left_edge / stripes, down=1.0), bottom),
                ],
            )
    rim = pygame.Rect(0, 0, 2 * top_half + SUPERSAMPLE, big * 0.08)
    rim.midtop = (round(centre_x), round(top - SUPERSAMPLE))
    pygame.draw.rect(surface, BUCKET_WHITE, rim, border_radius=SUPERSAMPLE)


@functools.cache
def player_picture(*, size: int, looking: Direction, mouth_fraction: float) -> pygame.Surface:
    """Draw Mr. Muncher: a popcorn bucket with eyes looking its way and a chomping mouth.

    Args:
        size: The picture's side, in pixels.
        looking: The direction its eyes look (the way it goes).
        mouth_fraction: 0.0 shut to 1.0 wide open.

    Returns:
        The picture, ``size`` square.

    """
    big = size * SUPERSAMPLE
    surface = pygame.Surface((big, big), pygame.SRCALPHA)
    _draw_bucket(surface=surface, big=big, height_fraction=1.0, popcorn=True)
    look_x, look_y = looking.step_x, looking.step_y
    for side in (-1, 1):
        eye = (
            big / 2 + side * big * FACE_EYE_SPACING_FRACTION + look_x * big * 0.03,
            big * FACE_EYE_Y_FRACTION + look_y * big * 0.03,
        )
        radius = big * FACE_EYE_RADIUS_FRACTION
        pygame.draw.circle(surface, EYE_OUTLINE_COLOR, eye, radius + SUPERSAMPLE)
        pygame.draw.circle(surface, EYE_WHITE_COLOR, eye, radius)
        pygame.draw.circle(
            surface,
            PUPIL_COLOR,
            (eye[0] + look_x * radius * 0.45, eye[1] + look_y * radius * 0.45),
            radius * 0.5,
        )
    mouth_height = big * (
        FACE_MOUTH_SHUT_FRACTION
        + (FACE_MOUTH_OPEN_FRACTION - FACE_MOUTH_SHUT_FRACTION) * mouth_fraction
    )
    mouth = pygame.Rect(0, 0, round(big * FACE_MOUTH_WIDTH_FRACTION), round(mouth_height))
    mouth.center = (round(big / 2 + look_x * big * 0.04), round(big * FACE_MOUTH_Y_FRACTION))
    pygame.draw.rect(surface, MOUTH_COLOR, mouth, border_radius=round(big * 0.05))
    if mouth_fraction > 0.0:
        teeth = 3
        tooth_half_width = big * 0.03
        for tooth in range(teeth):
            tooth_x = mouth.left + mouth.width * (tooth + 0.5) / teeth
            tooth_length = min(big * 0.05, mouth.height * 0.6)
            pygame.draw.polygon(
                surface,
                TOOTH_COLOR,
                [
                    (tooth_x - tooth_half_width, mouth.top),
                    (tooth_x + tooth_half_width, mouth.top),
                    (tooth_x, mouth.top + tooth_length),
                ],
            )
    return _smoothed(surface, size=(size, size))


@functools.cache
def player_dying_picture(*, size: int, progress: float) -> pygame.Surface:
    """Draw Mr. Muncher caught: the bucket sinks while its popcorn bursts out and fades.

    Args:
        size: The picture's side, in pixels.
        progress: 0.0 (just caught) to 1.0 (gone).

    Returns:
        The picture, ``size`` square (empty at 1.0).

    """
    big = size * SUPERSAMPLE
    surface = pygame.Surface((big, big), pygame.SRCALPHA)
    if progress < 1.0:
        _draw_bucket(
            surface=surface,
            big=big,
            height_fraction=1.0 - (1.0 - DYING_SQUASH_FRACTION) * progress,
            popcorn=False,
        )
        fade = round(255 * (1.0 - progress))
        for index, (puff_x, puff_y, radius) in enumerate(POPCORN_PUFFS):
            angle = 2 * math.pi * index / len(POPCORN_PUFFS) - math.pi / 2
            reach = big * 0.45 * progress
            pygame.draw.circle(
                surface,
                (*POPCORN_COLOR, fade),
                (big * puff_x + math.cos(angle) * reach, big * puff_y + math.sin(angle) * reach),
                big * radius * (1.0 - 0.5 * progress),
            )
    return _smoothed(surface, size=(size, size))


def _fuzz_body(*, big: int, color: Color, wave: int) -> pygame.Surface:
    """Draw a muncher's spiky round body at the supersampled size.

    Args:
        big: The supersampled side.
        color: The body colour.
        wave: 0 or 1: the spikes' frame (they shift a little as it moves).

    Returns:
        The supersampled body.

    """
    surface = pygame.Surface((big, big), pygame.SRCALPHA)
    centre = (big / 2, big / 2)
    outer = big / 2 - SUPERSAMPLE / 2
    inner = outer * FUZZ_INNER_FRACTION
    spike_step = math.pi / FUZZ_SPIKES
    points = [
        (
            centre[0] + math.cos(spike_step * (point + wave / 2)) * radius,
            centre[1] + math.sin(spike_step * (point + wave / 2)) * radius,
        )
        for point in range(FUZZ_SPIKES * 2)
        for radius in [outer if point % 2 == 0 else inner]
    ]
    pygame.draw.polygon(surface, color, points)
    pygame.draw.circle(surface, color, centre, inner + SUPERSAMPLE / 2)
    return surface


def _draw_eyes(*, surface: pygame.Surface, big: int, looking: Direction) -> None:
    """Draw a muncher's two eyes (whites and pupils) looking one way.

    Args:
        surface: The supersampled picture to draw on.
        big: Its side.
        looking: The direction the eyes look.

    """
    for side in (-1, 1):
        eye = (
            big / 2 + side * big * 0.15 + looking.step_x * big * 0.04,
            big * 0.42 + looking.step_y * big * 0.04,
        )
        pygame.draw.circle(surface, EYE_WHITE_COLOR, eye, big * 0.12)
        pygame.draw.circle(
            surface,
            PUPIL_COLOR,
            (eye[0] + looking.step_x * big * 0.05, eye[1] + looking.step_y * big * 0.05),
            big * 0.06,
        )


@functools.cache
def muncher_picture(*, size: int, color: Color, looking: Direction, wave: int) -> pygame.Surface:
    """Draw a muncher: a spiky fuzzball with angry brows, eyes looking its way, a jagged grin.

    Args:
        size: The picture's side, in pixels.
        color: The body colour.
        looking: The direction its eyes look.
        wave: 0 or 1: the spikes' frame.

    Returns:
        The picture, ``size`` square.

    """
    big = size * SUPERSAMPLE
    surface = _fuzz_body(big=big, color=color, wave=wave)
    _draw_eyes(surface=surface, big=big, looking=looking)
    brow_width = max(2, big // 28)
    for side in (-1, 1):
        pygame.draw.line(
            surface,
            BROW_COLOR,
            (big / 2 + side * big * 0.28, big * 0.25),
            (big / 2 + side * big * 0.05, big * 0.31),
            brow_width,
        )
    grin_points = 7
    grin = [
        (
            big / 2 - big * 0.2 + big * 0.4 * point / (grin_points - 1),
            big * 0.66 + (big * 0.06 if point % 2 else 0.0),
        )
        for point in range(grin_points)
    ]
    pygame.draw.polygon(
        surface,
        GRIN_COLOR,
        [*grin, (big / 2 + big * 0.2, big * 0.6), (big / 2 - big * 0.2, big * 0.6)],
    )
    pygame.draw.lines(surface, TOOTH_COLOR, closed=False, points=grin, width=brow_width)
    return _smoothed(surface, size=(size, size))


@functools.cache
def frightened_muncher_picture(*, size: int, flashing: bool, wave: int) -> pygame.Surface:
    """Draw a frightened muncher: a dull blue fuzzball (white when flashing) with a wobbly mouth.

    Args:
        size: The picture's side, in pixels.
        flashing: Draw the white "about to recover" colours.
        wave: 0 or 1: the spikes' frame.

    Returns:
        The picture, ``size`` square.

    """
    big = size * SUPERSAMPLE
    body_color, face_color = (
        (FLASHING_COLOR, FLASHING_FACE_COLOR)
        if flashing
        else (FRIGHTENED_COLOR, FRIGHTENED_FACE_COLOR)
    )
    surface = _fuzz_body(big=big, color=body_color, wave=wave)
    for side in (-1, 1):
        pygame.draw.circle(
            surface, face_color, (big / 2 + side * big * 0.15, big * 0.42), big * 0.06
        )
    mouth_points = 9
    mouth = [
        (
            big / 2 - big * 0.22 + big * 0.44 * point / (mouth_points - 1),
            big * 0.64 + (big * 0.04 if point % 2 else -big * 0.03),
        )
        for point in range(mouth_points)
    ]
    pygame.draw.lines(surface, face_color, closed=False, points=mouth, width=max(2, big // 28))
    return _smoothed(surface, size=(size, size))


@functools.cache
def eyes_picture(*, size: int, color: Color, looking: Direction) -> pygame.Surface:
    """Draw an eaten muncher going home: its eyes in a faint ring of its colour.

    Args:
        size: The picture's side, in pixels.
        color: The muncher's colour.
        looking: The direction the eyes look.

    Returns:
        The picture, ``size`` square.

    """
    big = size * SUPERSAMPLE
    surface = pygame.Surface((big, big), pygame.SRCALPHA)
    pygame.draw.circle(
        surface,
        (*color, EATEN_RING_ALPHA),
        (big / 2, big / 2),
        big / 2 - SUPERSAMPLE,
        width=SUPERSAMPLE * 2,
    )
    _draw_eyes(surface=surface, big=big, looking=looking)
    return _smoothed(surface, size=(size, size))


@functools.cache
def sprocket_picture(*, tile_size: int) -> pygame.Surface:
    """Draw a sprocket: a small rounded square, like a film strip's sprocket hole.

    Args:
        tile_size: A tile's side, in pixels.

    Returns:
        The picture, centred in a tile-sized square.

    """
    big = tile_size * SUPERSAMPLE
    surface = pygame.Surface((big, big), pygame.SRCALPHA)
    side = round(big * SPROCKET_SIZE_FRACTION)
    sprocket = pygame.Rect(0, 0, side, side)
    sprocket.center = (big // 2, big // 2)
    pygame.draw.rect(surface, SPROCKET_COLOR, sprocket, border_radius=side // 4)
    return _smoothed(surface, size=(tile_size, tile_size))


@functools.cache
def snack_picture(*, tile_size: int, lit: bool) -> pygame.Surface:
    """Draw a snack: a golden wrapped candy with a glow; it twinkles.

    Args:
        tile_size: A tile's side, in pixels.
        lit: True for the twinkle's bright half (the dim half is smaller and has no glow).

    Returns:
        The picture, centred in a square a tile and a half wide (the glow spills over).

    """
    side = tile_size * 3 // 2
    big = side * SUPERSAMPLE
    surface = pygame.Surface((big, big), pygame.SRCALPHA)
    centre = big / 2
    half_width = tile_size * SUPERSAMPLE * SNACK_SIZE_FRACTION / 2
    if lit:
        glow_rings = 4
        for ring in range(glow_rings, 0, -1):
            pygame.draw.circle(
                surface,
                (*SNACK_COLOR, 36 // ring),
                (centre, centre),
                half_width * (0.5 + 0.18 * ring),
            )
    else:
        half_width *= SNACK_DIM_FRACTION
    # The twisted wrapper's two ends, then the candy over them
    for side_sign in (-1, 1):
        pygame.draw.polygon(
            surface,
            SNACK_WRAPPER_COLOR,
            [
                (centre + side_sign * half_width * 0.4, centre),
                (centre + side_sign * half_width, centre - half_width * 0.45),
                (centre + side_sign * half_width, centre + half_width * 0.45),
            ],
        )
    candy = pygame.Rect(0, 0, round(half_width * 1.2), round(half_width * 0.9))
    candy.center = (round(centre), round(centre))
    pygame.draw.ellipse(surface, SNACK_COLOR, candy)
    pygame.draw.line(
        surface,
        SNACK_CORE_COLOR,
        (candy.left + candy.width * 0.3, candy.top + candy.height * 0.25),
        (candy.left + candy.width * 0.6, candy.top + candy.height * 0.25),
        max(1, round(half_width * 0.12)),
    )
    return _smoothed(surface, size=(side, side))


@functools.cache
def bonus_reel_picture(*, size: int) -> pygame.Surface:
    """Draw the bonus: a silver film reel with holes round its hub.

    Args:
        size: The picture's side, in pixels.

    Returns:
        The picture, ``size`` square.

    """
    big = size * SUPERSAMPLE
    surface = pygame.Surface((big, big), pygame.SRCALPHA)
    centre = (big / 2, big / 2)
    radius = big / 2 - SUPERSAMPLE
    pygame.draw.circle(surface, REEL_RIM_COLOR, centre, radius)
    pygame.draw.circle(surface, REEL_COLOR, centre, radius * 0.86)
    for hole in range(REEL_HOLE_COUNT):
        angle = 2 * math.pi * hole / REEL_HOLE_COUNT - math.pi / 2
        pygame.draw.circle(
            surface,
            (0, 0, 0, 0),
            (
                centre[0] + math.cos(angle) * radius * 0.5,
                centre[1] + math.sin(angle) * radius * 0.5,
            ),
            radius * 0.2,
        )
    pygame.draw.circle(surface, REEL_RIM_COLOR, centre, radius * 0.14)
    return _smoothed(surface, size=(size, size))


@functools.cache
def film_strip_panel(*, width: int, height: int, holes_on_left: bool) -> pygame.Surface:
    """Draw a side panel: the edge of a film strip, with a column of sprocket holes.

    Args:
        width: The panel's width, in pixels.
        height: Its height.
        holes_on_left: Put the holes along the left edge (else the right).

    Returns:
        The opaque panel.

    """
    panel = pygame.Surface((width, height), pygame.SRCALPHA)
    panel.fill((*FILM_COLOR, 255))
    hole_x = (
        SPROCKET_HOLE_MARGIN
        if holes_on_left
        else width - SPROCKET_HOLE_MARGIN - SPROCKET_HOLE_WIDTH
    )
    for hole_y in range(SPROCKET_HOLE_SPACING // 2, height, SPROCKET_HOLE_SPACING):
        pygame.draw.rect(
            panel,
            SPROCKET_HOLE_COLOR,
            (hole_x, hole_y - SPROCKET_HOLE_HEIGHT // 2, SPROCKET_HOLE_WIDTH, SPROCKET_HOLE_HEIGHT),
            border_radius=3,
        )
    return panel
