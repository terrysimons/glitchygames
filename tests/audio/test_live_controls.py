"""Tests for live instruments' controls: exposed parameters, routes, curves and smoothing.

Feature spec 5.4 and implementation spec 4.3 (M2); plans/2026-11-14-sound-migration.md.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from pydantic import ValidationError

from glitchygames.audio.live_controls import (
    MAXIMUM_ROUTES,
    ROUTE_DESTINATIONS,
    Parameter,
    Route,
    route_output,
    smoothed,
)


def test_a_parameter_clamps_to_its_range_and_says_when_it_did():
    """Values outside the range are clamped (and the caller counts each clamp)."""
    speed = Parameter(range=(0.0, 1.0), default=0.0)

    assert speed.clamped(0.5) == (0.5, False)
    assert speed.clamped(-1.0) == (0.0, True)
    assert speed.clamped(2.0) == (1.0, True)


@pytest.mark.parametrize(
    'arguments',
    [
        {'range': (1.0, 0.0), 'default': 0.5},  # backwards
        {'range': (0.0, 0.0), 'default': 0.0},  # empty
        {'range': (0.0, 1.0), 'default': 2.0},  # default outside
        {'range': (0.0, 1.0), 'default': 0.0, 'smoothing_ms': -1.0},
    ],
)
def test_a_parameter_that_cannot_work_is_refused(arguments):
    """A backwards or empty range, a default outside it, negative smoothing: refused."""
    with pytest.raises(ValidationError):
        Parameter(**arguments)


def test_a_parameters_default_smoothing_is_the_specs_30_ms():
    """The implementation spec's default glide."""
    assert Parameter(range=(0.0, 1.0), default=0.0).smoothing_ms == 30.0


@pytest.mark.parametrize(
    ('curve', 'fraction', 'expected'),
    [
        ('linear', 0.0, 100.0),
        ('linear', 0.25, 125.0),
        ('linear', 1.0, 200.0),
        ('exponential', 0.5, 100.0 * math.sqrt(2.0)),  # half way in ratio
        ('exponential', 1.0, 200.0),
        ('logarithmic', 0.0, 100.0),
        ('logarithmic', 1.0, 200.0),
        ('logarithmic', 0.5, 100.0 + 100.0 * math.log10(5.5)),
        ('smoothstep', 0.5, 150.0),
        ('smoothstep', 0.25, 100.0 + 100.0 * (3 * 0.0625 - 2 * 0.015625)),
        ('steps(4)', 0.0, 100.0),
        ('steps(4)', 0.3, 100.0 + 100.0 / 3),
        ('steps(4)', 0.99, 200.0),
        ('steps(4)', 1.0, 200.0),
    ],
)
def test_each_curve_maps_a_parameter_onto_the_output(curve, fraction, expected):
    """A parameter at a fraction of its range lands where its curve says on the output."""
    route = Route(source='speed', destination='pitch', curve=curve, output=(100.0, 200.0))
    parameter = Parameter(range=(0.0, 10.0), default=0.0)

    values = route_output(route=route, parameter=parameter, values=np.array([fraction * 10.0]))

    assert values[0] == pytest.approx(expected)


def test_a_curve_maps_whole_arrays_per_sample():
    """Routes run on a chunk's smoothed parameter, one value per sample."""
    route = Route(source='speed', destination='level', output=(0.0, 1.0))
    parameter = Parameter(range=(0.0, 1.0), default=0.0)

    values = route_output(route=route, parameter=parameter, values=np.linspace(0.0, 1.0, 5))

    np.testing.assert_allclose(values, np.linspace(0.0, 1.0, 5))


@pytest.mark.parametrize(
    'arguments',
    [
        {'destination': 'volume'},  # not a destination
        {'curve': 'wobbly'},
        {'curve': 'steps(1)'},
        {'curve': 'exponential', 'output': (0.0, 200.0)},  # a ratio needs positive ends
        {'curve': 'exponential', 'output': (-10.0, 200.0)},
    ],
)
def test_a_route_that_cannot_work_is_refused(arguments):
    """An unknown destination or curve, steps(1), a ratio through zero: refused."""
    route_arguments = {'source': 'speed', 'destination': 'pitch', 'output': (100.0, 200.0)}
    with pytest.raises(ValidationError):
        Route(**(route_arguments | arguments))


def test_the_destinations_are_the_ones_the_migration_built():
    """Sources' levels are named per source: sources.<name>.level."""
    assert set(ROUTE_DESTINATIONS) == {
        'pitch',
        'level',
        'filter.cutoff',
        'tremolo.rate',
        'tremolo.depth',
    }
    assert Route(source='load', destination='sources.air.level', output=(0.1, 0.5))
    assert MAXIMUM_ROUTES == 8


def test_smoothing_glides_one_pole_toward_the_target_per_sample():
    """Target + (start - target) * exp(-n / tau), from the first sample of the chunk."""
    values = smoothed(start=0.0, target=1.0, count=4, smoothing_ms=1000.0, sample_rate=4)

    expected = [1.0 - math.exp(-sample / 4.0) for sample in range(1, 5)]
    np.testing.assert_allclose(values, expected)


def test_without_smoothing_the_target_is_reached_at_once():
    """smoothing_ms 0 is a step to the target."""
    np.testing.assert_array_equal(
        smoothed(start=0.0, target=1.0, count=3, smoothing_ms=0.0, sample_rate=44100),
        [1.0, 1.0, 1.0],
    )


def test_a_jump_never_overshoots_and_moves_toward_the_target_every_sample():
    """No click: the glide is monotonic and stays between start and target."""
    values = smoothed(start=1.0, target=0.0, count=4410, smoothing_ms=30.0, sample_rate=44100)

    assert np.all(np.diff(values) < 0)
    assert values[0] < 1.0
    assert values[-1] > 0.0
