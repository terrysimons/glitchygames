"""Primitive-drawing helpers for all game visuals.

All game graphics are drawn from pygame primitives (no external assets).
Each function takes a Surface and draws onto it.
"""

from __future__ import annotations

import math

import pygame

from brave_adventurer.constants import (
    ARM_SWING_AMPLITUDE,
    COBRA_BODY,
    COBRA_EYE,
    COBRA_HOOD,
    GOLD_COLOR,
    GOLD_HIGHLIGHT,
    LEG_SWING_AMPLITUDE,
    PLAYER_BELT,
    PLAYER_CLOTH,
    PLAYER_HAIR,
    PLAYER_SKIN,
    SCARAB_BODY,
    SCORPION_BODY,
    SCORPION_TAIL,
)
from brave_adventurer_core.constants import (
    ANIMATION_SPEED,
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
# Collectible drawing
# ---------------------------------------------------------------------------


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

    # Coiled body (bottom-aligned so cobra sits on the ground)
    pygame.draw.ellipse(surface, COBRA_BODY, (2, height - 12, width - 4, 12))

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
