"""Tests for Drawing Fire's terrain: seeded hills over a flat baseline."""

from __future__ import annotations

import random

import pytest

from drawing_fire.terrain import (
    GROUND_BASELINE_FRACTION,
    HILL_HEIGHT_FRACTION_RANGE,
    build_terrain,
)


def test_terrain_has_hills_and_is_seeded():
    """The same seed gives the same ground, and a hill rises above the baseline."""
    first = build_terrain(width=800, height=480, random=random.Random(5))
    again = build_terrain(width=800, height=480, random=random.Random(5))
    assert first == again
    baseline = 480 * GROUND_BASELINE_FRACTION
    assert min(first.ground) < baseline - 480 * HILL_HEIGHT_FRACTION_RANGE[0] / 2  # a hill rises
    assert max(first.ground) <= baseline


@pytest.mark.parametrize(('width', 'height'), [(800, 480), (1280, 720), (320, 240)])
def test_terrain_spans_any_screen_width(width, height):
    """There is one ground y per pixel, and x outside the field is clamped to the edges."""
    terrain = build_terrain(width=width, height=height, random=random.Random(1))
    assert len(terrain.ground) == width
    assert 0 < terrain.ground_y(-50) == terrain.ground[0]
    assert terrain.ground_y(width + 50) == terrain.ground[-1]


def test_ground_y_interpolates_between_pixels():
    """Between two pixels the ground is the mean of the two."""
    terrain = build_terrain(width=800, height=480, random=random.Random(5))
    index = terrain.ground.index(min(terrain.ground)) - 1
    halfway = terrain.ground_y(index + 0.5)
    assert halfway == pytest.approx((terrain.ground[index] + terrain.ground[index + 1]) / 2)
