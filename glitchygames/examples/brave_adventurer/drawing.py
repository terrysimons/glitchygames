"""Primitive-drawing helpers for all game visuals.

All game graphics are drawn from pygame primitives (no external assets).
Each function takes a Surface and draws onto it.
"""

from __future__ import annotations

import math

import pygame

from glitchygames.examples.brave_adventurer.constants import (
    ANIMATION_SPEED,
    ARM_SWING_AMPLITUDE,
    COBRA_BODY,
    COBRA_EYE,
    COBRA_HOOD,
    DARK_SAND,
    GOLD_COLOR,
    GOLD_HIGHLIGHT,
    GRASS_COLOR,
    HORIZON_COLOR,
    LEG_SWING_AMPLITUDE,
    OASIS_GREEN,
    OASIS_TRUNK,
    OASIS_WATER,
    PLAYER_BELT,
    PLAYER_CLOTH,
    PLAYER_HAIR,
    PLAYER_SKIN,
    PYRAMID_COLOR,
    PYRAMID_SHADOW,
    ROCK_COLOR,
    SAND_COLOR,
    SCARAB_BODY,
    SCORPION_BODY,
    SCORPION_TAIL,
    SKY_COLOR,
    STONE_COLOR,
    STONE_MORTAR,
)

# ---------------------------------------------------------------------------
# Player drawing
# ---------------------------------------------------------------------------


def draw_player(
    surface: pygame.Surface,
    state: str,
    *,
    facing_right: bool,
    animation_timer: float,
) -> None:
    """Draw the adventurer character from primitives.

    Args:
        surface: The surface to draw onto (should be PLAYER_WIDTH x PLAYER_HEIGHT).
        state: One of 'idle', 'running', 'jumping', 'falling'.
        facing_right: True if the player faces right.
        animation_timer: Accumulated time for animation cycling.

    """
    width = surface.get_width()

    # We draw facing right, then flip if needed
    work_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

    center_x = width // 2

    # Head
    pygame.draw.circle(work_surface, PLAYER_SKIN, (center_x, 10), 8)

    # Hair arc on top of head
    hair_rect = pygame.Rect(center_x - 8, 2, 16, 12)
    pygame.draw.arc(work_surface, PLAYER_HAIR, hair_rect, 0, math.pi, 3)

    # Torso
    pygame.draw.rect(work_surface, PLAYER_CLOTH, (center_x - 8, 18, 16, 16))

    # Belt
    pygame.draw.rect(work_surface, PLAYER_BELT, (center_x - 8, 30, 16, 3))

    # Legs with animation
    leg_offset = 0.0
    if state == 'running':
        leg_offset = math.sin(animation_timer * ANIMATION_SPEED) * LEG_SWING_AMPLITUDE
    elif state == 'jumping':
        leg_offset = -3.0
    elif state == 'falling':
        leg_offset = 2.0

    # Left leg
    left_foot_x = center_x - 4 - round(leg_offset)
    pygame.draw.line(
        work_surface,
        PLAYER_SKIN,
        (center_x - 4, 33),
        (left_foot_x, 46),
        3,
    )
    # Right leg
    right_foot_x = center_x + 4 + round(leg_offset)
    pygame.draw.line(
        work_surface,
        PLAYER_SKIN,
        (center_x + 4, 33),
        (right_foot_x, 46),
        3,
    )

    # Arms
    if state == 'jumping':
        # Arms raised up
        pygame.draw.line(work_surface, PLAYER_SKIN, (center_x - 8, 20), (center_x - 14, 10), 2)
        pygame.draw.line(work_surface, PLAYER_SKIN, (center_x + 8, 20), (center_x + 14, 10), 2)
    elif state == 'falling':
        # Arms out to sides
        pygame.draw.line(work_surface, PLAYER_SKIN, (center_x - 8, 20), (center_x - 16, 18), 2)
        pygame.draw.line(work_surface, PLAYER_SKIN, (center_x + 8, 20), (center_x + 16, 18), 2)
    else:
        # Arms swinging (or at rest for idle)
        arm_swing = (
            math.sin(animation_timer * ANIMATION_SPEED) * ARM_SWING_AMPLITUDE
            if state == 'running'
            else 0.0
        )
        pygame.draw.line(
            work_surface,
            PLAYER_SKIN,
            (center_x - 8, 20),
            (center_x - 12, 30 + round(arm_swing)),
            2,
        )
        pygame.draw.line(
            work_surface,
            PLAYER_SKIN,
            (center_x + 8, 20),
            (center_x + 12, 30 - round(arm_swing)),
            2,
        )

    # Flip if facing left
    if not facing_right:
        work_surface = pygame.transform.flip(work_surface, flip_x=True, flip_y=False)

    surface.blit(work_surface, (0, 0))


# ---------------------------------------------------------------------------
# Terrain drawing
# ---------------------------------------------------------------------------


def draw_ground_segment(surface: pygame.Surface, width: int) -> None:
    """Draw a sand-colored ground segment with a darker top edge.

    Args:
        surface: The surface to draw onto.
        width: Width of the ground segment.

    """
    surface.fill(SAND_COLOR)
    # Darker top edge to give depth
    pygame.draw.line(surface, DARK_SAND, (0, 0), (width - 1, 0), 3)
    # Subtle texture lines
    for x_position in range(0, width, 40):
        pygame.draw.line(surface, DARK_SAND, (x_position, 8), (x_position + 20, 8), 1)


def draw_stone_wall(surface: pygame.Surface, width: int, height: int) -> None:
    """Draw a stone wall with a block pattern.

    Args:
        surface: The surface to draw onto.
        width: Width of the wall.
        height: Height of the wall.

    """
    surface.fill(STONE_COLOR)
    block_height = 16
    block_width = 16

    for row in range(0, height, block_height):
        # Offset every other row for a brick pattern
        offset = block_width // 2 if (row // block_height) % 2 else 0
        for column in range(-offset, width, block_width):
            pygame.draw.rect(
                surface,
                STONE_MORTAR,
                (column, row, block_width, block_height),
                1,
            )


def draw_gold_scarab(surface: pygame.Surface) -> None:
    """Draw a shimmering gold collectible scarab.

    Args:
        surface: The surface to draw onto (GOLD_SCARAB_SIZE x GOLD_SCARAB_SIZE).

    """
    size = surface.get_width()
    # Body
    pygame.draw.ellipse(surface, GOLD_COLOR, (2, 2, size - 4, size - 4))
    # Wing line
    pygame.draw.line(
        surface,
        GOLD_HIGHLIGHT,
        (size // 2, 3),
        (size // 2, size - 3),
        1,
    )
    # Head dot
    pygame.draw.circle(surface, GOLD_HIGHLIGHT, (size // 2, 3), 2)


# ---------------------------------------------------------------------------
# Enemy drawing
# ---------------------------------------------------------------------------


def draw_cobra(surface: pygame.Surface, *, striking: bool, animation_timer: float) -> None:
    """Draw a cobra from primitives.

    Args:
        surface: The surface to draw onto.
        striking: True if the cobra is in its strike pose.
        animation_timer: Time accumulator for idle bob animation.

    """
    width = surface.get_width()
    height = surface.get_height()

    # Coiled body
    pygame.draw.ellipse(surface, COBRA_BODY, (2, height - 14, width - 4, 12))

    # Hood / head section (raised up)
    if striking:
        # Head lunges forward and up
        hood_y = 0
        hood_width = width - 4
    else:
        # Gentle bob
        bob = math.sin(animation_timer * 3) * 2
        hood_y = round(4 + bob)
        hood_width = width - 8

    hood_x = (width - hood_width) // 2
    pygame.draw.ellipse(surface, COBRA_HOOD, (hood_x, hood_y, hood_width, height - 16))

    # Eyes
    eye_y = hood_y + 6
    pygame.draw.circle(surface, COBRA_EYE, (width // 2 - 3, eye_y), 2)
    pygame.draw.circle(surface, COBRA_EYE, (width // 2 + 3, eye_y), 2)


def draw_scarab(surface: pygame.Surface, roll_angle: float) -> None:
    """Draw a scarab beetle from primitives.

    Args:
        surface: The surface to draw onto.
        roll_angle: Rotation angle for the rolling animation.

    """
    width = surface.get_width()
    height = surface.get_height()

    # Body oval
    pygame.draw.ellipse(surface, SCARAB_BODY, (2, 2, width - 4, height - 4))

    # Wing line (rotates slightly to suggest rolling)
    center_x = width // 2
    center_y = height // 2
    line_offset = round(math.sin(roll_angle) * 3)
    pygame.draw.line(
        surface,
        GOLD_COLOR,
        (center_x, 3),
        (center_x + line_offset, height - 3),
        1,
    )

    # Legs
    for y_offset in [-2, 0, 2]:
        left_start = (2, center_y + y_offset)
        left_end = (0, center_y + y_offset + 2)
        pygame.draw.line(surface, SCARAB_BODY, left_start, left_end, 1)
        right_start = (width - 2, center_y + y_offset)
        right_end = (width, center_y + y_offset + 2)
        pygame.draw.line(surface, SCARAB_BODY, right_start, right_end, 1)


def draw_scorpion(surface: pygame.Surface, *, facing_right: bool) -> None:
    """Draw a scorpion from primitives.

    Args:
        surface: The surface to draw onto.
        facing_right: True if the scorpion faces right.

    """
    height = surface.get_height()

    work_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

    # Body segments
    pygame.draw.ellipse(work_surface, SCORPION_BODY, (6, height - 12, 16, 10))

    # Tail (curved arc rising up from the back)
    tail_rect = pygame.Rect(16, 0, 12, height - 4)
    pygame.draw.arc(work_surface, SCORPION_TAIL, tail_rect, -0.5, math.pi * 0.8, 2)

    # Stinger dot at tail tip
    pygame.draw.circle(work_surface, SCORPION_TAIL, (22, 2), 2)

    # Front claws
    pygame.draw.line(work_surface, SCORPION_BODY, (6, height - 8), (0, height - 14), 2)
    pygame.draw.line(work_surface, SCORPION_BODY, (6, height - 6), (0, height - 4), 2)

    # Legs
    for y_offset in [0, 3, 6]:
        pygame.draw.line(
            work_surface,
            SCORPION_BODY,
            (10, height - 4 + y_offset - 6),
            (8, height + y_offset - 6 + 3),
            1,
        )
        pygame.draw.line(
            work_surface,
            SCORPION_BODY,
            (18, height - 4 + y_offset - 6),
            (20, height + y_offset - 6 + 3),
            1,
        )

    if not facing_right:
        work_surface = pygame.transform.flip(work_surface, flip_x=True, flip_y=False)

    surface.blit(work_surface, (0, 0))


# ---------------------------------------------------------------------------
# Background / parallax drawing
# ---------------------------------------------------------------------------


def draw_sky(surface: pygame.Surface, _offset: float) -> None:
    """Draw a gradient sky from blue at top to pale yellow at horizon.

    This is static (scroll_factor=0) so offset is ignored.
    Intended to be called once and cached.

    Args:
        surface: The surface to draw onto.
        _offset: Parallax offset (unused for static sky).

    """
    height = surface.get_height()
    width = surface.get_width()
    sky_r, sky_g, sky_b = SKY_COLOR
    horizon_r, horizon_g, horizon_b = HORIZON_COLOR

    for y_position in range(height):
        interpolation = y_position / max(height - 1, 1)
        red = round(sky_r + (horizon_r - sky_r) * interpolation)
        green = round(sky_g + (horizon_g - sky_g) * interpolation)
        blue = round(sky_b + (horizon_b - sky_b) * interpolation)
        pygame.draw.line(surface, (red, green, blue), (0, y_position), (width, y_position))


def draw_pyramids(surface: pygame.Surface, offset: float) -> None:
    """Draw large pyramids that scroll slowly across the background.

    Pyramids are spaced across a repeating 2400px world segment.

    Args:
        surface: The surface to draw onto.
        offset: Parallax-adjusted scroll offset.

    """
    repeat_width = 2400

    pyramid_definitions = [
        (400, 140, 180),  # (world_x, base_half_width, height)
        (1000, 100, 130),
        (1800, 160, 200),
    ]

    for pyramid_world_x, base_half, pyramid_height in pyramid_definitions:
        screen_x = (pyramid_world_x - offset) % repeat_width - repeat_width // 4
        base_y = 380

        # Main face (lit side)
        lit_points = [
            (round(screen_x - base_half), base_y),
            (round(screen_x + base_half), base_y),
            (round(screen_x), base_y - pyramid_height),
        ]
        pygame.draw.polygon(surface, PYRAMID_COLOR, lit_points)

        # Shadow face (right side darker)
        shadow_points = [
            (round(screen_x), base_y - pyramid_height),
            (round(screen_x + base_half), base_y),
            (round(screen_x + base_half // 3), base_y),
        ]
        pygame.draw.polygon(surface, PYRAMID_SHADOW, shadow_points)


def draw_dunes_and_oasis(surface: pygame.Surface, offset: float) -> None:
    """Draw rolling sand dunes and occasional oases.

    Args:
        surface: The surface to draw onto.
        offset: Parallax-adjusted scroll offset.

    """
    width = surface.get_width()
    height = surface.get_height()

    # Draw dune shapes using layered sine waves
    for x_pixel in range(width):
        world_x = x_pixel + offset
        dune_y = 360 + round(
            math.sin(world_x * 0.005) * 20
            + math.sin(world_x * 0.013) * 10
            + math.sin(world_x * 0.002) * 15
        )
        dune_y = min(dune_y, height)
        if dune_y < height:
            pygame.draw.line(surface, SAND_COLOR, (x_pixel, dune_y), (x_pixel, height))

    # Draw oases at fixed world positions (repeating every 3000 px)
    oasis_repeat = 3000
    for oasis_base_x in [800, 2200]:
        screen_x = round((oasis_base_x - offset) % oasis_repeat - oasis_repeat // 4)

        # Only draw if roughly on screen
        oasis_draw_margin = 100
        if -oasis_draw_margin < screen_x < width + oasis_draw_margin:
            # Small pool of water
            pygame.draw.ellipse(surface, OASIS_WATER, (screen_x - 30, 370, 60, 15))

            # Palm tree trunk
            pygame.draw.line(surface, OASIS_TRUNK, (screen_x, 370), (screen_x - 8, 330), 3)

            # Palm fronds (radiating lines with green circles)
            frond_base_x = screen_x - 8
            frond_base_y = 330
            for angle_degrees in [-60, -30, 0, 30, 60]:
                radians = math.radians(angle_degrees - 90)
                tip_x = frond_base_x + round(math.cos(radians) * 20)
                tip_y = frond_base_y + round(math.sin(radians) * 20)
                frond_start = (frond_base_x, frond_base_y)
                pygame.draw.line(surface, OASIS_GREEN, frond_start, (tip_x, tip_y), 2)
                pygame.draw.circle(surface, OASIS_GREEN, (tip_x, tip_y), 5)


def draw_near_ground_details(surface: pygame.Surface, offset: float) -> None:
    """Draw small rocks and grass tufts on the near ground layer.

    Args:
        surface: The surface to draw onto.
        offset: Parallax-adjusted scroll offset.

    """
    width = surface.get_width()

    # Place rocks and grass at pseudo-random but deterministic positions
    # based on world position. Use a simple hash-like approach.
    detail_spacing = 60
    rounded_offset = round(offset)
    start_world_x = (rounded_offset // detail_spacing) * detail_spacing

    for world_x in range(start_world_x, start_world_x + width + detail_spacing, detail_spacing):
        screen_x = world_x - rounded_offset

        # Deterministic pseudo-random using world position
        seed = (world_x * 7919) % 1000
        detail_y = 392 + (seed % 8)

        if seed % 3 == 0:
            # Small rock
            rock_width = 6 + (seed % 5)
            rock_height = 4 + (seed % 3)
            pygame.draw.ellipse(
                surface,
                ROCK_COLOR,
                (screen_x, detail_y, rock_width, rock_height),
            )
        elif seed % 3 == 1:
            # Grass tuft
            for blade in range(3):
                blade_x = screen_x + blade * 3
                blade_height = 6 + (seed + blade) % 4
                pygame.draw.line(
                    surface,
                    GRASS_COLOR,
                    (blade_x, detail_y),
                    (blade_x + 1, detail_y - blade_height),
                    1,
                )
