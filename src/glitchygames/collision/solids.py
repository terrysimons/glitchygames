"""Solid collision primitives: the rules games use to keep sprites out of solids.

Detection is ``CollisionManager``'s; these decide what a game does once a sprite overlaps a solid
(ground, a wall, a platform, a paddle), so every game resolves with the same rules
(plans/2026-11-02-solid-collision.md):

- ``entered_from_left``: which side of a solid an overlapping mover came in from, from where it
  was before this frame's move (Brave Adventurer's walls, the ball's paddles).
- ``world_x_flush_left_of`` / ``world_x_flush_right_of``: the world x that puts a sprite's
  collision rect flush against a solid's side (walls, pit edges, a scarab turning).
- ``feet_land_on_surface``: a swept landing test, so a long tick cannot carry falling feet
  through a surface (Clockwork Keep's platforms, BUGS.md #205).

They take plain numbers, so each game keeps its own measures (a snapped or raw position, an
integer or a float centre) and resolves exactly as before.
"""

from __future__ import annotations


def entered_from_left(  # ruff: ignore[too-many-arguments]
    *,
    mover_left: float,
    mover_right: float,
    displacement_x: float,
    solid_left: float,
    solid_right: float,
    mover_center_x: float,
    solid_center_x: float,
) -> bool:
    """Decide which side of a solid an overlapping mover is pushed out of.

    Looks at where the mover was before this frame's move (its edges less ``displacement_x``):
    clear of the solid on one side means it came in from that side, even when a long frame
    carried its centre past the solid's centre. If it already overlapped (it widened, or is
    not moving), the side of the solid's centre its own centre is on decides, so it is pushed
    out on its own side, never through the solid.

    Args:
        mover_left: The mover's left edge now.
        mover_right: The mover's right edge now.
        displacement_x: How far it moved in x this frame (velocity times the frame's dt).
        solid_left: The solid's left edge.
        solid_right: The solid's right edge.
        mover_center_x: The mover's centre, as the game measures it.
        solid_center_x: The solid's centre, as the game measures it.

    Returns:
        True to push the mover out to the solid's left, False to its right.

    """
    previous_left = mover_left - displacement_x
    previous_right = mover_right - displacement_x
    if previous_right <= solid_left:
        return True
    if previous_left >= solid_right:
        return False
    return mover_center_x < solid_center_x


def world_x_flush_left_of(
    *, solid_left: int, collision_offset_x: int, collision_width: int
) -> float:
    """Return the world x putting a sprite's collision rect flush against a solid's left side.

    Args:
        solid_left: The solid's left edge.
        collision_offset_x: The collision rect's x offset from the sprite's (snapped) world x
            (``collision_rect_offset``).
        collision_width: The collision rect's width.

    Returns:
        The sprite's world x.

    """
    return float(solid_left - (collision_offset_x + collision_width))


def world_x_flush_right_of(*, solid_right: int, collision_offset_x: int) -> float:
    """Return the world x putting a sprite's collision rect flush against a solid's right side.

    Args:
        solid_right: The solid's right edge.
        collision_offset_x: The collision rect's x offset from the sprite's (snapped) world x
            (``collision_rect_offset``).

    Returns:
        The sprite's world x.

    """
    return float(solid_right - collision_offset_x)


def feet_land_on_surface(
    *,
    velocity_y: float,
    feet_now: float,
    feet_start: float,
    surface_top: float,
    tolerance: float,
) -> bool:
    """Whether falling (or standing) feet land on a surface this tick, swept from their start.

    They land when they end the tick at or below the surface's top, and started it no more than
    ``tolerance`` below it; a rising sprite never lands (a one-way surface is jumped through).

    Args:
        velocity_y: The sprite's vertical velocity (positive falls).
        feet_now: The feet's world y now.
        feet_start: The feet's world y before the tick (``feet_now`` when unknown).
        surface_top: The surface's top.
        tolerance: How far below the top the feet may have started and still land.

    Returns:
        True if the feet land on the surface.

    """
    if velocity_y < 0 or feet_now < surface_top:
        return False
    return feet_start <= surface_top + tolerance
