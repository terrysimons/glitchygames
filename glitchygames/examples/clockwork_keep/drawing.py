"""Primitive-drawing helpers for Clockwork Keep.

All graphics drawn from pygame primitives. Steampunk tower interior
with walls, windows showing sky, and machinery in the background.
"""

from __future__ import annotations

import math

import pygame

from glitchygames.examples.clockwork_keep.constants import (
    ANIMATION_SPEED,
    ARM_SWING_AMPLITUDE,
    CLOCK_BRASS,
    CLOCK_CENTER_CAP_RADIUS,
    CLOCK_HOUR_HAND_LENGTH,
    CLOCK_HOUR_HAND_WIDTH,
    CLOCK_MINUTE_HAND_LENGTH,
    CLOCK_MINUTE_HAND_WIDTH,
    CLOCK_SECOND_HAND,
    CLOCK_SECOND_HAND_LENGTH,
    CLOCK_SECOND_HAND_TAIL_LENGTH,
    CLOCK_SECOND_HAND_WIDTH,
    CLOCK_SECONDS_PER_HALF_DAY,
    CLOCK_SECONDS_PER_HOUR,
    CLOCK_SECONDS_PER_MINUTE,
    CLOCK_START_SECONDS,
    LEG_SWING_AMPLITUDE,
    PLAYER_BOOTS,
    PLAYER_GOGGLE_FRAME,
    PLAYER_GOGGLE_LENS,
    PLAYER_SKIN,
    PLAYER_VEST,
    PLAYER_WRENCH,
    PLAYFIELD_LEFT,
    PLAYFIELD_RIGHT,
    PLAYFIELD_WIDTH,
    WALL_WIDTH,
)

# ---------------------------------------------------------------------------
# Player: The Tinker
# ---------------------------------------------------------------------------


def draw_tinker(
    surface: pygame.Surface,
    state: str,
    *,
    facing_right: bool,
    animation_timer: float,
) -> None:
    """Draw the Tinker character from primitives.

    Args:
        surface: Surface to draw onto (PLAYER_WIDTH x PLAYER_HEIGHT).
        state: One of 'idle', 'running', 'jumping', 'falling'.
        facing_right: True if facing right.
        animation_timer: Accumulated time for animation cycling.

    """
    width = surface.get_width()
    work = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    center_x = width // 2

    # Head
    pygame.draw.circle(work, PLAYER_SKIN, (center_x, 10), 7)

    # Goggles
    pygame.draw.circle(work, PLAYER_GOGGLE_FRAME, (center_x - 4, 8), 4)
    pygame.draw.circle(work, PLAYER_GOGGLE_FRAME, (center_x + 4, 8), 4)
    pygame.draw.circle(work, PLAYER_GOGGLE_LENS, (center_x - 4, 8), 3)
    pygame.draw.circle(work, PLAYER_GOGGLE_LENS, (center_x + 4, 8), 3)
    pygame.draw.line(work, PLAYER_GOGGLE_FRAME, (center_x - 8, 8), (center_x + 8, 8), 1)

    # Vest / torso
    pygame.draw.rect(work, PLAYER_VEST, (center_x - 7, 17, 14, 14))

    # Belt with buckle
    pygame.draw.rect(work, (60, 40, 20), (center_x - 7, 28, 14, 3))
    pygame.draw.rect(work, (180, 160, 60), (center_x - 2, 28, 4, 3))

    # Legs
    leg_offset = 0.0
    if state == 'running':
        leg_offset = math.sin(animation_timer * ANIMATION_SPEED) * LEG_SWING_AMPLITUDE
    elif state == 'jumping':
        leg_offset = -3.0
    elif state == 'falling':
        leg_offset = 2.0

    left_foot_x = center_x - 4 - round(leg_offset)
    pygame.draw.line(work, PLAYER_SKIN, (center_x - 4, 31), (left_foot_x, 38), 2)
    pygame.draw.rect(work, PLAYER_BOOTS, (left_foot_x - 2, 38, 5, 4))

    right_foot_x = center_x + 4 + round(leg_offset)
    pygame.draw.line(work, PLAYER_SKIN, (center_x + 4, 31), (right_foot_x, 38), 2)
    pygame.draw.rect(work, PLAYER_BOOTS, (right_foot_x - 2, 38, 5, 4))

    # Arms
    arm_offset = 0.0
    if state == 'running':
        arm_offset = math.sin(animation_timer * ANIMATION_SPEED + math.pi) * ARM_SWING_AMPLITUDE

    pygame.draw.line(
        work,
        PLAYER_SKIN,
        (center_x - 7, 19),
        (center_x - 10 - round(arm_offset), 28),
        2,
    )

    wrench_x = center_x + 10 + round(arm_offset)
    wrench_y = 28
    pygame.draw.line(work, PLAYER_SKIN, (center_x + 7, 19), (wrench_x, wrench_y), 2)
    wrench_top = wrench_y - 5
    pygame.draw.line(work, PLAYER_WRENCH, (wrench_x, wrench_y), (wrench_x + 3, wrench_top), 2)
    pygame.draw.line(work, PLAYER_WRENCH, (wrench_x + 1, wrench_top), (wrench_x + 5, wrench_top), 2)

    if not facing_right:
        work = pygame.transform.flip(work, flip_x=True, flip_y=False)

    surface.blit(work, (0, 0))


# ---------------------------------------------------------------------------
# Terrain
# ---------------------------------------------------------------------------


def draw_platform(
    surface: pygame.Surface,
    platform_color: tuple[int, int, int],
    top_color: tuple[int, int, int],
) -> None:
    """Draw a metallic platform.

    Args:
        surface: Surface to draw onto.
        platform_color: Main body color.
        top_color: Highlighted top edge color.

    """
    width = surface.get_width()
    surface.fill(platform_color)
    pygame.draw.rect(surface, top_color, (0, 0, width, 3))
    rivet_spacing = 20
    for x_pos in range(10, width, rivet_spacing):
        pygame.draw.circle(surface, (60, 60, 60), (x_pos, 6), 2)


def draw_elevator(surface: pygame.Surface) -> None:
    """Draw an elevator platform with caution stripes and up-arrow.

    Args:
        surface: Surface to draw onto.

    """
    width = surface.get_width()
    height = surface.get_height()
    surface.fill((120, 100, 50))
    stripe_width = 8
    for x_pos in range(0, width, stripe_width * 2):
        pygame.draw.rect(surface, (180, 150, 40), (x_pos, 0, stripe_width, height))
    center_x = width // 2
    pygame.draw.polygon(
        surface,
        (255, 255, 200),
        [(center_x, 1), (center_x - 4, height - 1), (center_x + 4, height - 1)],
    )


def draw_cog_collectible(
    surface: pygame.Surface,
    color: tuple[int, int, int],
    rotation: float,
) -> None:
    """Draw a collectible cog (static — bobbing is done by moving the sprite).

    Args:
        surface: Surface to draw onto (COG_SIZE x COG_SIZE).
        color: Cog color.
        rotation: Rotation angle in radians for gear tooth animation.

    """
    size = surface.get_width()
    center = size // 2

    # Gear teeth around the edge
    tooth_radius = center - 2
    body_radius = center - 4
    teeth = 8
    for i in range(teeth):
        angle = (2 * math.pi * i / teeth) + rotation
        tooth_x = center + round(tooth_radius * math.cos(angle))
        tooth_y = center + round(tooth_radius * math.sin(angle))
        pygame.draw.circle(surface, color, (tooth_x, tooth_y), 2)

    # Inner body
    pygame.draw.circle(surface, color, (center, center), body_radius)
    # Center axle hole
    pygame.draw.circle(surface, (0, 0, 0, 0), (center, center), 2)


# ---------------------------------------------------------------------------
# Tower backgrounds — called by Camera2D parallax system
# Each receives (surface, camera_x, camera_y)
# ---------------------------------------------------------------------------


def _draw_tower_walls(
    surface: pygame.Surface,
    camera_y: float,
    wall_color: tuple[int, int, int],
    accent_color: tuple[int, int, int],
    window_sky_color: tuple[int, int, int],
) -> None:
    """Draw tower walls with brick pattern and windows.

    Args:
        surface: Surface to draw onto.
        camera_y: Vertical camera position for scrolling brick/window pattern.
        wall_color: Main wall color.
        accent_color: Brick mortar / accent color.
        window_sky_color: Color visible through windows.

    """
    height = surface.get_height()

    # Left wall
    pygame.draw.rect(surface, wall_color, (0, 0, WALL_WIDTH, height))
    # Right wall
    pygame.draw.rect(surface, wall_color, (PLAYFIELD_RIGHT, 0, WALL_WIDTH, height))

    # Brick pattern (horizontal lines)
    brick_height = 20
    y_offset = round(camera_y) % brick_height
    for wall_y in range(-y_offset, height + brick_height, brick_height):
        pygame.draw.line(surface, accent_color, (0, wall_y), (WALL_WIDTH, wall_y), 1)
        pygame.draw.line(
            surface,
            accent_color,
            (PLAYFIELD_RIGHT, wall_y),
            (PLAYFIELD_RIGHT + WALL_WIDTH, wall_y),
            1,
        )

    # Windows (periodic openings showing sky)
    window_height = 40
    window_width = 50
    window_spacing = 160
    window_y_offset = round(camera_y) % window_spacing
    for win_y in range(-window_y_offset, height + window_spacing, window_spacing):
        # Left wall window
        win_x_left = (WALL_WIDTH - window_width) // 2
        pygame.draw.rect(
            surface,
            window_sky_color,
            (win_x_left, win_y, window_width, window_height),
        )
        # Window frame
        pygame.draw.rect(
            surface,
            accent_color,
            (win_x_left, win_y, window_width, window_height),
            2,
        )
        # Cross bars
        mid_x = win_x_left + window_width // 2
        mid_y = win_y + window_height // 2
        win_right_edge = win_x_left + window_width
        pygame.draw.line(surface, accent_color, (win_x_left, mid_y), (win_right_edge, mid_y), 1)
        pygame.draw.line(surface, accent_color, (mid_x, win_y), (mid_x, win_y + window_height), 1)

        # Right wall window
        win_x_right = PLAYFIELD_RIGHT + (WALL_WIDTH - window_width) // 2
        pygame.draw.rect(
            surface,
            window_sky_color,
            (win_x_right, win_y, window_width, window_height),
        )
        pygame.draw.rect(
            surface,
            accent_color,
            (win_x_right, win_y, window_width, window_height),
            2,
        )
        mid_x_r = win_x_right + window_width // 2
        win_right_edge_r = win_x_right + window_width
        pygame.draw.line(surface, accent_color, (win_x_right, mid_y), (win_right_edge_r, mid_y), 1)
        win_bottom = win_y + window_height
        pygame.draw.line(surface, accent_color, (mid_x_r, win_y), (mid_x_r, win_bottom), 1)


def draw_boiler_background(
    surface: pygame.Surface,
    _camera_x: float,
    camera_y: float,
) -> None:
    """Draw Boiler Room background — furnace glow, pipes, and tower walls.

    Args:
        surface: Surface to draw onto.
        _camera_x: Horizontal camera (unused — tower is 1 screen wide).
        camera_y: Vertical camera position.

    """
    from glitchygames.examples.clockwork_keep.constants import (
        BOILER_BG,
        BOILER_GLOW,
        BOILER_WALL,
        BOILER_WALL_ACCENT,
        BOILER_WINDOW_SKY,
    )

    surface.fill(BOILER_BG)
    height = surface.get_height()

    # Distant vertical pipes in the playfield background
    pipe_color = (50, 35, 20)
    pipe_spacing = 80
    for pipe_x in range(PLAYFIELD_LEFT + 30, PLAYFIELD_RIGHT, pipe_spacing):
        pygame.draw.rect(surface, pipe_color, (pipe_x, 0, 6, height))

    # Furnace glow at bottom of view
    glow_y = height - 30 + round(camera_y * 0.05)
    for glow_x in range(PLAYFIELD_LEFT + 50, PLAYFIELD_RIGHT - 50, 150):
        pygame.draw.ellipse(surface, BOILER_GLOW, (glow_x, glow_y, 60, 20))

    # Tower walls with windows
    _draw_tower_walls(surface, camera_y, BOILER_WALL, BOILER_WALL_ACCENT, BOILER_WINDOW_SKY)


def draw_gear_background(
    surface: pygame.Surface,
    _camera_x: float,
    camera_y: float,
) -> None:
    """Draw Gear Works background — gears and machinery behind platforms.

    Args:
        surface: Surface to draw onto.
        _camera_x: Horizontal camera (unused).
        camera_y: Vertical camera position.

    """
    from glitchygames.examples.clockwork_keep.constants import (
        GEAR_BG,
        GEAR_COPPER,
        GEAR_WALL,
        GEAR_WALL_ACCENT,
        GEAR_WINDOW_SKY,
    )

    surface.fill(GEAR_BG)
    height = surface.get_height()

    # Background gears (large, slow-spinning silhouettes)
    gear_color = (45, 45, 50)
    gear_spacing = 200
    y_offset = round(camera_y * 0.15) % gear_spacing
    for gy in range(-y_offset, height + gear_spacing, gear_spacing):
        for gx in [250, 550]:
            pygame.draw.circle(surface, gear_color, (gx, gy), 40, 3)
            # Gear teeth
            for t in range(12):
                angle = 2 * math.pi * t / 12
                tx = gx + round(44 * math.cos(angle))
                ty = gy + round(44 * math.sin(angle))
                pygame.draw.circle(surface, gear_color, (tx, ty), 4)

    # Copper chain running vertically
    chain_x = 400
    link_height = 12
    chain_offset = round(camera_y * 0.2) % (link_height * 2)
    for chain_y in range(-chain_offset, height + link_height * 2, link_height * 2):
        pygame.draw.ellipse(surface, GEAR_COPPER, (chain_x - 4, chain_y, 8, link_height), 2)

    _draw_tower_walls(surface, camera_y, GEAR_WALL, GEAR_WALL_ACCENT, GEAR_WINDOW_SKY)


def clock_hand_angles(clock_seconds: float) -> tuple[float, float, float]:
    """Return the hour, minute and second hand angles for a time on a 12-hour dial.

    The hands sweep smoothly: each one advances continuously with the fractional seconds.

    Args:
        clock_seconds: Seconds since midnight (wraps every 12 hours).

    Returns:
        (hour, minute, second) angles in radians, clockwise from 12 o'clock.

    """
    full_turn = 2 * math.pi
    hour_angle = (
        full_turn * (clock_seconds % CLOCK_SECONDS_PER_HALF_DAY) / CLOCK_SECONDS_PER_HALF_DAY
    )
    minute_angle = full_turn * (clock_seconds % CLOCK_SECONDS_PER_HOUR) / CLOCK_SECONDS_PER_HOUR
    second_angle = full_turn * (clock_seconds % CLOCK_SECONDS_PER_MINUTE) / CLOCK_SECONDS_PER_MINUTE
    return (hour_angle, minute_angle, second_angle)


def _clock_hand_end(center: tuple[int, int], *, clock_angle: float, length: int) -> tuple[int, int]:
    """Return the pixel at length from center along a clockwise-from-12 angle."""
    screen_angle = clock_angle - math.pi / 2
    return (
        center[0] + round(length * math.cos(screen_angle)),
        center[1] + round(length * math.sin(screen_angle)),
    )


def draw_clock_background(
    surface: pygame.Surface,
    _camera_x: float,
    camera_y: float,
    *,
    clock_seconds: float = CLOCK_START_SECONDS,
) -> None:
    """Draw Clock Face background — midnight blue with a working clock.

    Args:
        surface: Surface to draw onto.
        _camera_x: Horizontal camera (unused).
        camera_y: Vertical camera position.
        clock_seconds: Seconds since midnight shown by the hands (12-hour dial).

    """
    from glitchygames.examples.clockwork_keep.constants import (
        CLOCK_BG,
        CLOCK_WALL,
        CLOCK_WALL_ACCENT,
        CLOCK_WINDOW_SKY,
    )

    surface.fill(CLOCK_BG)
    height = surface.get_height()

    # Large clock face centered in background
    center_x = PLAYFIELD_LEFT + PLAYFIELD_WIDTH // 2
    center_y = height // 2 - round(camera_y * 0.05)
    clock_radius = 120

    pygame.draw.circle(surface, (20, 20, 45), (center_x, center_y), clock_radius, 3)

    # Hour markers
    for i in range(12):
        angle = 2 * math.pi * i / 12 - math.pi / 2
        mx = center_x + round((clock_radius - 15) * math.cos(angle))
        my = center_y + round((clock_radius - 15) * math.sin(angle))
        pygame.draw.circle(surface, (35, 35, 60), (mx, my), 4)

    # Clock hands, sweeping smoothly with clock_seconds
    center = (center_x, center_y)
    hour_angle, minute_angle, second_angle = clock_hand_angles(clock_seconds)
    pygame.draw.line(
        surface,
        CLOCK_BRASS,
        center,
        _clock_hand_end(center, clock_angle=hour_angle, length=CLOCK_HOUR_HAND_LENGTH),
        CLOCK_HOUR_HAND_WIDTH,
    )
    pygame.draw.line(
        surface,
        CLOCK_BRASS,
        center,
        _clock_hand_end(center, clock_angle=minute_angle, length=CLOCK_MINUTE_HAND_LENGTH),
        CLOCK_MINUTE_HAND_WIDTH,
    )
    pygame.draw.line(
        surface,
        CLOCK_SECOND_HAND,
        _clock_hand_end(
            center, clock_angle=second_angle + math.pi, length=CLOCK_SECOND_HAND_TAIL_LENGTH
        ),
        _clock_hand_end(center, clock_angle=second_angle, length=CLOCK_SECOND_HAND_LENGTH),
        CLOCK_SECOND_HAND_WIDTH,
    )
    pygame.draw.circle(surface, CLOCK_BRASS, center, CLOCK_CENTER_CAP_RADIUS)

    # Pendulum chains
    for px in [300, 500]:
        pygame.draw.line(surface, (30, 30, 50), (px, 0), (px, height), 1)

    _draw_tower_walls(surface, camera_y, CLOCK_WALL, CLOCK_WALL_ACCENT, CLOCK_WINDOW_SKY)
