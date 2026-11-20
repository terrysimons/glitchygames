"""Tests for Drawing Fire's terrain: seeded hills over a flat baseline."""

from __future__ import annotations

import math
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


def _reference_ground_y(*, ground, x):
    """Worked from the definition: clamp to the field, then interpolate between two pixels."""
    clamped_x = min(max(x, 0.0), float(len(ground) - 1))
    left_index = math.floor(clamped_x)
    right_index = min(left_index + 1, len(ground) - 1)
    fraction = clamped_x - left_index
    return ground[left_index] * (1.0 - fraction) + ground[right_index] * fraction


@pytest.mark.parametrize('seed', range(4))
@pytest.mark.parametrize('width', [1, 2, 320, 800])
def test_ground_y_equals_the_clamp_and_interpolate_definition_bit_for_bit(seed, width):
    """Every x, edges and outside the field included, gives exactly the definition's float.

    ground_y is written as comparisons for speed; recorded replays depend on its exact bits
    (the line-of-sight test decides what soldiers do), so this compares with ==, not approx.
    """
    terrain = build_terrain(width=width, height=480, random=random.Random(seed))
    generator = random.Random(seed)
    last = float(width - 1)
    sampled = [generator.uniform(-20.0, width + 20.0) for _ in range(500)]
    edges = [-1e9, -1.0, -0.0, 0.0, 0.5, last - 0.5, last, last + 1e-9, width + 1e9, 3, -3]
    edges += [float(index) for index in range(width)]
    for x in [*sampled, *edges]:
        assert terrain.ground_y(x) == _reference_ground_y(ground=terrain.ground, x=x)
