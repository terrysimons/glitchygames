"""Solid collision primitives (glitchygames/collision/solids.py)."""

from __future__ import annotations

import pytest

from glitchygames.collision.solids import (
    entered_from_left,
    feet_land_on_surface,
    world_x_flush_left_of,
    world_x_flush_right_of,
)

# A solid from x=100 to x=120 (centre 110); a mover 10 wide
SOLID = {'solid_left': 100, 'solid_right': 120, 'solid_center_x': 110.0}


class TestEnteredFromLeft:
    """Where the mover was before its move decides; overlapping already, the centres do."""

    @pytest.mark.parametrize(
        ('mover_left', 'displacement_x', 'mover_center_x', 'expected'),
        [
            (95, 10, 100, True),  # was clear on the left (85..95)
            (115, -10, 120, False),  # was clear on the right (125..135)
            (112, 30, 117, True),  # a long frame carried its centre past the solid's
            (98, 0, 103, True),  # not moving, overlapping: its centre is left of the solid's
            (108, 0, 113, False),  # not moving, overlapping: its centre is right of it
        ],
        ids=['from-left', 'from-right', 'long-frame', 'still-left', 'still-right'],
    )
    def test_the_side(self, mover_left, displacement_x, mover_center_x, expected):
        assert (
            entered_from_left(
                mover_left=mover_left,
                mover_right=mover_left + 10,
                displacement_x=displacement_x,
                mover_center_x=mover_center_x,
                **SOLID,
            )
            is expected
        )


class TestFlushPlacement:
    """The world x that puts a collision rect against a solid's side."""

    def test_flush_left_of_a_solid(self):
        """The rect (offset 3, width 10) ends at the solid's left edge."""
        world_x = world_x_flush_left_of(solid_left=100, collision_offset_x=3, collision_width=10)

        assert world_x == 87.0
        assert world_x + 3 + 10 == 100

    def test_flush_right_of_a_solid(self):
        """The rect (offset 3) starts at the solid's right edge."""
        world_x = world_x_flush_right_of(solid_right=120, collision_offset_x=3)

        assert world_x == 117.0
        assert isinstance(world_x, float)


class TestFeetLandOnSurface:
    """A swept landing: falling feet that reached the top land, however far the tick took them."""

    @pytest.mark.parametrize(
        ('velocity_y', 'feet_now', 'feet_start', 'expected'),
        [
            (300.0, 205.0, 190.0, True),  # fell through the top this tick
            (300.0, 240.0, 150.0, True),  # a long tick: far past the top, still lands
            (0.0, 200.0, 200.0, True),  # standing on it
            (300.0, 195.0, 190.0, False),  # still above the top
            (-300.0, 205.0, 210.0, False),  # rising: jumps up through it
            (300.0, 230.0, 220.0, False),  # started well below the top: under it, not on it
        ],
        ids=['falls-on', 'long-tick', 'standing', 'above', 'rising', 'from-below'],
    )
    def test_landing(self, velocity_y, feet_now, feet_start, expected):
        assert (
            feet_land_on_surface(
                velocity_y=velocity_y,
                feet_now=feet_now,
                feet_start=feet_start,
                surface_top=200.0,
                tolerance=4.0,
            )
            is expected
        )
