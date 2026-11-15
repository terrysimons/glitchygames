"""Live instruments' controls: exposed parameters, routes, curves and smoothing (M2).

Feature spec 5.3-5.4 and implementation spec 4.3; plans/2026-11-14-sound-migration.md. A live
instrument exposes named ``Parameter``s a game sets while it plays (``LiveSoundHandle.set``),
and ``Route``s map each onto what the sound does. ``Parameter`` and ``Route`` mirror the TOML
schema (``[instruments.x.parameters.<name>]``, ``[[instruments.x.routes]]``) one to one.

Rules:

1. A value outside a parameter's range is clamped (``Parameter.clamped`` says when, so the caller
   counts it).
2. A route maps its parameter's fraction of the range, ``f``, onto its output ``(a, b)`` by its
   curve (the specs name the curves; their shapes are defined here):

   - ``linear``: ``a + (b - a) * f``
   - ``exponential``: ``a * (b / a) ** f``, even steps in ratio (octaves, filter sweeps); both
     ends must be positive
   - ``logarithmic``: ``a + (b - a) * log10(1 + 9 f)``, rising fast, then flattening
   - ``smoothstep``: ``a + (b - a) * (3 f**2 - 2 f**3)``
   - ``steps(n)``: ``n`` even levels from ``a`` to ``b`` (``n`` at least 2)

3. Destinations: ``pitch`` (Hz), ``level`` (0-1, multiplied in), ``filter.cutoff`` (Hz),
   ``tremolo.rate`` (Hz), ``tremolo.depth`` (0-1) and ``sources.<name>.level``; at most
   ``MAXIMUM_ROUTES`` per instrument. A route's source is an exposed parameter, so no cycle can
   form (the specs' envelope and LFO sources are later work).
4. Smoothing is a one-pole glide per sample, ``target + (start - target) * exp(-n / tau)`` with
   ``tau`` the parameter's ``smoothing_ms`` in samples, so a jump never clicks; 0 reaches the
   target at once. Updates coalesce: the voice reads the latest value once per chunk.

This module is a leaf: numpy, pydantic and the standard library.
"""

from __future__ import annotations

import re
from typing import Final, Self

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FloatArray = npt.NDArray[np.float64]

# Rule 3
ROUTE_DESTINATIONS: Final[tuple[str, ...]] = (
    'pitch',
    'level',
    'filter.cutoff',
    'tremolo.rate',
    'tremolo.depth',
)
SOURCE_LEVEL_DESTINATION: Final[re.Pattern[str]] = re.compile(
    r'sources\.(?P<name>[A-Za-z0-9_]+)\.level'
)
MAXIMUM_ROUTES: Final[int] = 8
# The spec's default smoothing (implementation spec 6.1)
DEFAULT_SMOOTHING_MS: Final[float] = 30.0
# Rule 2
CURVES: Final[tuple[str, ...]] = ('linear', 'exponential', 'logarithmic', 'smoothstep')
STEPS_CURVE: Final[re.Pattern[str]] = re.compile(r'steps\((?P<count>\d+)\)')
MINIMUM_STEPS: Final[int] = 2
LOGARITHMIC_SPREAD: Final[float] = 9.0
MILLISECONDS_PER_SECOND: Final[float] = 1000.0


class Parameter(BaseModel):
    """A value a game sets on a live sound while it plays (rules 1 and 4)."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    range: tuple[float, float]
    default: float
    smoothing_ms: float = Field(default=DEFAULT_SMOOTHING_MS, ge=0.0)
    unit: str = ''

    @model_validator(mode='after')
    def _a_usable_range(self) -> Self:
        low, high = self.range
        if not low < high:
            message = f'a parameter range runs low to high, got {self.range}'
            raise ValueError(message)
        if not low <= self.default <= high:
            message = f'the default {self.default} is outside the range {self.range}'
            raise ValueError(message)
        return self

    def clamped(self, value: float) -> tuple[float, bool]:
        """Clamp a value to the range (rule 1).

        Returns:
            The value within the range, and whether it had to be clamped.
        """
        low, high = self.range
        inside = min(max(value, low), high)
        return inside, inside != value


class Route(BaseModel):
    """A parameter mapped onto something the sound does (rules 2 and 3)."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    source: str
    destination: str
    curve: str = 'linear'
    output: tuple[float, float]

    @field_validator('destination')
    @classmethod
    def _a_known_destination(cls, value: str) -> str:
        if value not in ROUTE_DESTINATIONS and SOURCE_LEVEL_DESTINATION.fullmatch(value) is None:
            known = ', '.join((*ROUTE_DESTINATIONS, 'sources.<name>.level'))
            message = f'unknown destination {value!r}; destinations are {known}'
            raise ValueError(message)
        return value

    @field_validator('curve')
    @classmethod
    def _a_known_curve(cls, value: str) -> str:
        steps = STEPS_CURVE.fullmatch(value)
        if steps is not None and int(steps.group('count')) >= MINIMUM_STEPS:
            return value
        if value not in CURVES:
            message = (
                f'unknown curve {value!r}; curves are {", ".join(CURVES)} and steps(n) for n '
                f'of at least {MINIMUM_STEPS}'
            )
            raise ValueError(message)
        return value

    @model_validator(mode='after')
    def _a_ratio_needs_positive_ends(self) -> Self:
        if self.curve == 'exponential' and not (self.output[0] > 0.0 and self.output[1] > 0.0):
            message = f'an exponential curve needs positive output ends, got {self.output}'
            raise ValueError(message)
        return self


def route_output(*, route: Route, parameter: Parameter, values: FloatArray) -> FloatArray:
    """Map a parameter's values onto a route's output by its curve (rule 2), per sample.

    Args:
        route: The route.
        parameter: Its source parameter.
        values: The parameter's values (one per sample), within its range.

    Returns:
        The output values.
    """
    low, high = parameter.range
    fraction = np.clip((values - low) / (high - low), 0.0, 1.0)
    start, end = route.output
    steps = STEPS_CURVE.fullmatch(route.curve)
    if steps is not None:
        count = int(steps.group('count'))
        shaped = np.floor(np.minimum(fraction * count, count - 1)) / (count - 1)
    elif route.curve == 'exponential':
        return start * (end / start) ** fraction
    elif route.curve == 'logarithmic':
        shaped = np.log10(1.0 + LOGARITHMIC_SPREAD * fraction)
    elif route.curve == 'smoothstep':
        shaped = fraction * fraction * (3.0 - 2.0 * fraction)
    else:
        shaped = fraction
    return start + (end - start) * shaped


def smoothed(
    *, start: float, target: float, count: int, smoothing_ms: float, sample_rate: int
) -> FloatArray:
    """Glide one pole from ``start`` toward ``target`` over ``count`` samples (rule 4).

    Returns:
        The value at each sample, the first one sample after ``start``.
    """
    if smoothing_ms <= 0.0:
        return np.full(count, target, dtype=np.float64)
    tau = smoothing_ms * sample_rate / MILLISECONDS_PER_SECOND
    samples = np.arange(1, count + 1, dtype=np.float64)
    return target + (start - target) * np.exp(-samples / tau)
