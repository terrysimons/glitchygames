"""Named waves, blends, harmonics, wave points and the wave registry.

A ``Wave`` is one cycle of a shape held in a 2048-sample table. Built-in names are ``sine``,
``triangle``, ``saw``, ``square``, ``pulse_12``, ``pulse_25``, ``pulse_75`` and ``pulse`` (with an
explicit ``duty``). ``saw``, ``square`` and the pulses are stored as naive shapes and flagged
``is_built_in_polyblep``: the renderer draws those with the PolyBLEP oscillator in
``glitchygames.audio.synth`` instead of reading their tables. Every other wave (mixes, blends,
harmonics, points) is rendered from its band-limited mip tables.

Mip tables: for each octave band from 20 Hz up to Nyquist, the wave's spectrum is truncated to
the harmonics that fit below Nyquist at the band's highest frequency, then transformed back into a
2048-sample table. Bands are built lazily and cached on the wave.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Self, override

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from numpy.typing import NDArray

log: logging.Logger = logging.getLogger('game.audio.waves')

WAVE_TABLE_LENGTH: Final[int] = 2048
BUILT_IN_WAVE_NAMES: Final[tuple[str, ...]] = (
    'sine',
    'triangle',
    'saw',
    'square',
    'pulse_12',
    'pulse_25',
    'pulse_75',
    'pulse',
)
BUILT_IN_DUTIES: Final[dict[str, float]] = {
    'square': 0.5,
    'pulse_12': 0.125,
    'pulse_25': 0.25,
    'pulse_75': 0.75,
    'pulse': 0.5,
}
POLYBLEP_WAVE_NAMES: Final[frozenset[str]] = frozenset({'saw', *BUILT_IN_DUTIES})
DUTY_LOWEST: Final[float] = 0.01
DUTY_HIGHEST: Final[float] = 0.99
LOWEST_BAND_HERTZ: Final[float] = 20.0
HIGHEST_TABLE_HARMONIC: Final[int] = WAVE_TABLE_LENGTH // 2
FLAT_WAVE_TOLERANCE: Final[float] = 1e-12
SILENT_LEVEL: Final[float] = 0.0
DRAWBAR_DIGIT_COUNT: Final[int] = 9
DRAWBAR_LEVEL_STEPS: Final[float] = 8.0
POINT_SHAPES: Final[tuple[str, ...]] = ('linear', 'smooth', 'steps')
# Fritsch-Carlson: a slope pair outside this circle (radius 3) can overshoot
FRITSCH_CARLSON_CIRCLE_RADIUS: Final[float] = 3.0

type FloatArray = NDArray[np.float64]


class CYCLE:
    """Named positions across one cycle, from 0 to 1."""

    START = 0.0
    EIGHTH = 0.125
    QUARTER = 0.25
    THREE_EIGHTHS = 0.375
    HALF = 0.5
    FIVE_EIGHTHS = 0.625
    THREE_QUARTERS = 0.75
    SEVEN_EIGHTHS = 0.875
    END = 1.0


class LEVEL:
    """Named heights of a wave, from -1 to 1."""

    TOP = 1.0
    HIGH = 0.5
    CENTER = 0.0
    LOW = -0.5
    BOTTOM = -1.0


@dataclass(frozen=True)
class WavePoint:
    """One point of a wave: where in the cycle, and how high."""

    at: float  # position in the cycle, 0-1
    level: float  # -1 to 1


@dataclass(frozen=True, kw_only=True)
class Harmonics:
    """How loud each overtone is, by its musical name (level 0 is silent).

    The harmonic number is the multiple of the note's frequency. ``sub_octave`` (harmonic 0.5,
    the 16' drawbar) and ``fifth`` (harmonic 1.5, the 5 1/3' drawbar) lie below or between the
    fundamental's overtones, so a one-cycle table of the fundamental cannot hold them. When
    either is present, the table's cycle is one period of the lowest tone (half the
    fundamental's frequency): the 16' bar then sits at bin 1 of the 2048-sample table and the 8'
    bar (``fundamental``) at bin 2. Without them, the fundamental is bin 1.
    """

    sub_octave: float = 0.0  # harmonic 0.5 (16' bar)
    fifth: float = 0.0  # harmonic 1.5 (5 1/3' bar)
    fundamental: float = 1.0  # harmonic 1 (8' bar)
    octave: float = 0.0  # harmonic 2
    octave_and_fifth: float = 0.0  # harmonic 3
    two_octaves: float = 0.0  # harmonic 4
    harmonic_5: float = 0.0  # harmonic 5
    harmonic_6: float = 0.0  # harmonic 6
    harmonic_7: float = 0.0  # harmonic 7
    harmonic_8: float = 0.0  # harmonic 8
    harmonic_9: float = 0.0  # harmonic 9
    harmonic_10: float = 0.0  # harmonic 10
    harmonic_11: float = 0.0  # harmonic 11
    harmonic_12: float = 0.0  # harmonic 12
    harmonic_13: float = 0.0  # harmonic 13
    harmonic_14: float = 0.0  # harmonic 14
    harmonic_15: float = 0.0  # harmonic 15
    harmonic_16: float = 0.0  # harmonic 16
    harmonic_17: float = 0.0  # harmonic 17
    harmonic_18: float = 0.0  # harmonic 18
    harmonic_19: float = 0.0  # harmonic 19
    harmonic_20: float = 0.0  # harmonic 20
    harmonic_21: float = 0.0  # harmonic 21
    harmonic_22: float = 0.0  # harmonic 22
    harmonic_23: float = 0.0  # harmonic 23
    harmonic_24: float = 0.0  # harmonic 24
    harmonic_25: float = 0.0  # harmonic 25
    harmonic_26: float = 0.0  # harmonic 26
    harmonic_27: float = 0.0  # harmonic 27
    harmonic_28: float = 0.0  # harmonic 28
    harmonic_29: float = 0.0  # harmonic 29
    harmonic_30: float = 0.0  # harmonic 30
    harmonic_31: float = 0.0  # harmonic 31
    harmonic_32: float = 0.0  # harmonic 32

    @classmethod
    def drawbars(cls, setting: str) -> Self:
        """Read an organ drawbar setting: nine digits, each 0-8 (level digit / 8).

        The drawbar order is 16', 5 1/3', 8', 4', 2 2/3', 2', 1 3/5', 1 1/3', 1', which are
        harmonics 0.5, 1.5, 1, 2, 3, 4, 5, 6 and 8.

        Args:
            setting: Nine digit characters, for example ``'008000000'``.

        Returns:
            The matching harmonic levels.

        Raises:
            ValueError: If the setting is not nine digits of 0-8.
        """
        if len(setting) != DRAWBAR_DIGIT_COUNT or not all(
            character in '012345678' for character in setting
        ):
            message = f'drawbars need {DRAWBAR_DIGIT_COUNT} digits from 0 to 8, got {setting!r}'
            raise ValueError(message)
        levels = [int(character) / DRAWBAR_LEVEL_STEPS for character in setting]
        return cls(
            sub_octave=levels[0],
            fifth=levels[1],
            fundamental=levels[2],
            octave=levels[3],
            octave_and_fifth=levels[4],
            two_octaves=levels[5],
            harmonic_5=levels[6],
            harmonic_6=levels[7],
            harmonic_8=levels[8],
        )

    def levels_by_harmonic(self) -> dict[float, float]:
        """The nonzero levels, keyed by harmonic number (0.5, 1, 1.5, 2, ...).

        Returns:
            Harmonic number to level.
        """
        named_levels: dict[float, float] = {
            0.5: self.sub_octave,
            1.5: self.fifth,
            1.0: self.fundamental,
            2.0: self.octave,
            3.0: self.octave_and_fifth,
            4.0: self.two_octaves,
        }
        for harmonic in range(5, 33):
            named_levels[float(harmonic)] = getattr(self, f'harmonic_{harmonic}')
        return {
            harmonic: level
            for harmonic, level in sorted(named_levels.items())
            if abs(level) > SILENT_LEVEL
        }


def _freeze(table: FloatArray) -> FloatArray:
    table.setflags(write=False)
    return table


def _normalized(table: FloatArray) -> FloatArray:
    return table / np.max(np.abs(table))


def _naive_table(name: str, duty: float | None) -> FloatArray:
    phase = np.arange(WAVE_TABLE_LENGTH) / WAVE_TABLE_LENGTH
    if name == 'sine':
        return np.sin(2.0 * np.pi * phase)
    if name == 'triangle':
        # Starts at 0, peaks at 1 a quarter in, bottoms at -1 three quarters in
        return 1.0 - 4.0 * np.abs((phase + 0.25) % 1.0 - 0.5)
    if name == 'saw':
        return 2.0 * phase - 1.0
    assert duty is not None
    return np.where(phase < duty, 1.0, -1.0)


def _monotone_cubic(
    positions: FloatArray, points_at: FloatArray, points_level: FloatArray
) -> FloatArray:
    """Evaluate a monotone cubic Hermite spline through the points.

    Args:
        positions: Where to sample, within the first and last point.
        points_at: Strictly increasing point positions.
        points_level: The point levels.

    Returns:
        The spline at each position.
    """
    # Monotone cubic: F. N. Fritsch and R. E. Carlson, SIAM J. Numer. Anal. 17(2), 1980
    widths = np.diff(points_at)
    secants = np.diff(points_level) / widths
    slopes = np.empty_like(points_level)
    slopes[0] = secants[0]
    slopes[-1] = secants[-1]
    slopes[1:-1] = 0.5 * (secants[:-1] + secants[1:])
    # A sign change between neighbouring secants is a local extremum: flat there
    slopes[1:-1][secants[:-1] * secants[1:] <= 0.0] = 0.0
    for interval, secant in enumerate(secants):
        if abs(secant) < FLAT_WAVE_TOLERANCE:
            slopes[interval] = 0.0
            slopes[interval + 1] = 0.0
            continue
        alpha = slopes[interval] / secant
        beta = slopes[interval + 1] / secant
        squared_length = alpha * alpha + beta * beta
        if squared_length > FRITSCH_CARLSON_CIRCLE_RADIUS**2:
            scale = FRITSCH_CARLSON_CIRCLE_RADIUS / math.sqrt(squared_length)
            slopes[interval] = scale * alpha * secant
            slopes[interval + 1] = scale * beta * secant
    index = np.clip(np.searchsorted(points_at, positions, side='right') - 1, 0, len(widths) - 1)
    width = widths[index]
    fraction = (positions - points_at[index]) / width
    cube = fraction**3
    square = fraction**2
    return (
        (2.0 * cube - 3.0 * square + 1.0) * points_level[index]
        + (cube - 2.0 * square + fraction) * width * slopes[index]
        + (-2.0 * cube + 3.0 * square) * points_level[index + 1]
        + (cube - square) * width * slopes[index + 1]
    )


class Wave:
    """One cycle of a shape: immutable, hashable by its table bytes.

    ``Wave('sine')``, ``Wave('pulse', duty=0.125)``, ``Wave.mix(square=0.6, triangle=0.4)``,
    ``Wave('saw').blend('sine', amount=0.3)``, ``Wave.from_harmonics(...)`` and
    ``Wave.from_points(...)`` all give a wave; ``table()`` is its 2048-sample cycle.
    """

    __slots__ = ('_bands', '_built_in_name', '_duty', '_table')

    def __init__(self, name: str, *, duty: float | None = None) -> None:
        """Build a built-in wave by name.

        Args:
            name: One of ``BUILT_IN_WAVE_NAMES``.
            duty: High fraction (0.01-0.99), for ``pulse`` only.

        Raises:
            ValueError: On an unknown name, a duty on a name that has none, or a duty outside
                0.01-0.99.
        """
        if name not in BUILT_IN_WAVE_NAMES:
            message = f'unknown wave {name!r}; built-in waves are {", ".join(BUILT_IN_WAVE_NAMES)}'
            raise ValueError(message)
        if duty is not None and name != 'pulse':
            message = f'duty only applies to the pulse wave, not {name!r}'
            raise ValueError(message)
        if duty is not None and not DUTY_LOWEST <= duty <= DUTY_HIGHEST:
            message = f'duty must be between {DUTY_LOWEST} and {DUTY_HIGHEST}, got {duty}'
            raise ValueError(message)
        resolved_duty = duty if duty is not None else BUILT_IN_DUTIES.get(name)
        self._initialize(
            table=_naive_table(name, resolved_duty), built_in_name=name, duty=resolved_duty
        )

    def _initialize(
        self, *, table: FloatArray, built_in_name: str | None, duty: float | None
    ) -> None:
        self._table: FloatArray = _freeze(table)
        self._built_in_name: str | None = built_in_name
        self._duty: float | None = duty
        self._bands: dict[int, FloatArray] = {}

    @classmethod
    def _from_table(cls, table: FloatArray) -> Self:
        wave = cls.__new__(cls)
        wave._initialize(table=table, built_in_name=None, duty=None)
        return wave

    @property
    def name(self) -> str | None:
        """The built-in name, or None for a mix, blend, harmonics or points wave."""
        return self._built_in_name

    @property
    def duty(self) -> float | None:
        """The high fraction of a square or pulse wave, else None."""
        return self._duty

    @property
    def is_built_in_polyblep(self) -> bool:
        """True for ``saw``, ``square`` and ``pulse*``, which render through PolyBLEP."""
        return self._built_in_name in POLYBLEP_WAVE_NAMES

    def table(self) -> FloatArray:
        """The wave's cycle.

        Returns:
            A read-only array of ``WAVE_TABLE_LENGTH`` float64 samples.
        """
        return self._table

    def band_limited_table(self, *, highest_frequency: float, sample_rate: int) -> FloatArray:
        """The mip table for the octave band holding ``highest_frequency``.

        The band's top frequency is 20 Hz times a power of two at or above
        ``highest_frequency``. Only the harmonics that stay below Nyquist at that top are kept.
        A table whose cycle holds sub-harmonics (see ``Harmonics``) is read at its own cycle
        frequency, so the frequencies here are those of the table's cycle.

        Args:
            highest_frequency: The highest cycle frequency, in hertz, that will read the table.
            sample_rate: Samples per second.

        Returns:
            A read-only array of ``WAVE_TABLE_LENGTH`` samples.

        Raises:
            ValueError: If the frequency is not positive or is above Nyquist.
        """
        nyquist = sample_rate / 2.0
        if not 0.0 < highest_frequency <= nyquist:
            message = f'highest_frequency must be in (0, {nyquist}], got {highest_frequency}'
            raise ValueError(message)
        band_index = max(0, math.ceil(math.log2(highest_frequency / LOWEST_BAND_HERTZ)))
        band_top = LOWEST_BAND_HERTZ * 2.0**band_index
        kept_harmonics = min(max(1, math.floor(nyquist / band_top)), HIGHEST_TABLE_HARMONIC)
        if kept_harmonics not in self._bands:
            spectrum = np.fft.rfft(self._table)
            spectrum[kept_harmonics + 1 :] = 0.0
            self._bands[kept_harmonics] = _freeze(np.fft.irfft(spectrum, n=WAVE_TABLE_LENGTH))
        return self._bands[kept_harmonics]

    @classmethod
    def mix(cls, **weights: float) -> Self:
        """Mix built-in waves by name; weights are normalized and the result peaks at 1.

        Args:
            **weights: Built-in wave name to weight. To mix registered waves too, use
                ``WaveRegistry.mix``.

        Returns:
            The mixed wave.
        """
        return cls.mix_resolved(weights=weights, resolve=cls)

    @classmethod
    def mix_resolved(cls, *, weights: Mapping[str, float], resolve: Callable[[str], Wave]) -> Self:
        """Mix waves found by name through ``resolve``; weights are normalized, peak is 1.

        Args:
            weights: Wave name to weight.
            resolve: Looks a name up (``WaveRegistry.__getitem__`` for registered waves).

        Returns:
            The mixed wave.

        Raises:
            ValueError: If there are no weights, a weight is negative, or all are zero.
        """
        if not weights:
            message = 'mix needs at least one wave'
            raise ValueError(message)
        if any(weight < 0.0 for weight in weights.values()):
            message = 'mix weights cannot be negative'
            raise ValueError(message)
        total = sum(weights.values())
        if total <= 0.0:
            message = 'mix weights must not all be zero'
            raise ValueError(message)
        mixed = sum((weight / total) * resolve(name).table() for name, weight in weights.items())
        return cls._from_table(_normalized(np.asarray(mixed)))

    def blend(self, other: str | Wave, *, amount: float) -> Wave:
        """Crossfade toward another wave: amount 0 is this wave, 1 is the other.

        The result is normalized to peak at 1, like ``mix``.

        Args:
            other: A built-in wave name or a wave.
            amount: 0 to 1.

        Returns:
            The blended wave.

        Raises:
            ValueError: If the amount is outside 0-1.
        """
        if not 0.0 <= amount <= 1.0:
            message = f'amount must be between 0 and 1, got {amount}'
            raise ValueError(message)
        other_wave = Wave(other) if isinstance(other, str) else other
        blended = (1.0 - amount) * self._table + amount * other_wave.table()
        return type(self)._from_table(_normalized(blended))

    @classmethod
    def from_harmonics(cls, harmonics: Harmonics) -> Self:
        """Add sine harmonics into one cycle; the result peaks at 1.

        When ``sub_octave`` or ``fifth`` is nonzero the cycle is one period of the lowest tone
        (see ``Harmonics``): harmonic ``h`` sits at table bin ``2 * h``.

        Args:
            harmonics: The overtone levels.

        Returns:
            The wave.

        Raises:
            ValueError: If a level is negative or every level is zero.
        """
        levels = harmonics.levels_by_harmonic()
        if not levels:
            message = 'harmonics has no variation: every level is zero'
            raise ValueError(message)
        if any(level < 0.0 for level in levels.values()):
            message = 'harmonic levels cannot be negative'
            raise ValueError(message)
        bins_per_harmonic = 2 if harmonics.sub_octave or harmonics.fifth else 1
        phase = np.arange(WAVE_TABLE_LENGTH) / WAVE_TABLE_LENGTH
        table = np.zeros(WAVE_TABLE_LENGTH)
        for harmonic, level in levels.items():
            table += level * np.sin(2.0 * np.pi * harmonic * bins_per_harmonic * phase)
        return cls._from_table(_normalized(table))

    @classmethod
    def from_points(
        cls, points: Sequence[WavePoint], *, shape: str = 'linear', normalize: bool = True
    ) -> Self:
        """Draw one cycle through points; the DC offset is removed.

        Args:
            points: At least two points, strictly increasing in ``at``, the first at 0 and the
                last at 1, each level within -1 to 1.
            shape: ``'linear'`` (piecewise linear), ``'smooth'`` (monotone cubic, never
                overshoots between points) or ``'steps'`` (sample and hold).
            normalize: Scale the result so its peak is 1.

        Returns:
            The wave.

        Raises:
            ValueError: On a bad shape or points, or a wave with no variation.
        """
        if shape not in POINT_SHAPES:
            message = f'shape must be one of {POINT_SHAPES}, got {shape!r}'
            raise ValueError(message)
        if len(points) < 2:  # ruff: ignore[magic-value-comparison]
            message = 'a wave needs at least two points'
            raise ValueError(message)
        points_at = np.array([point.at for point in points], dtype=np.float64)
        points_level = np.array([point.level for point in points], dtype=np.float64)
        if points_at[0] != CYCLE.START or points_at[-1] != CYCLE.END:
            message = 'points must start at CYCLE.START and end at CYCLE.END'
            raise ValueError(message)
        if np.any(np.diff(points_at) <= 0.0):
            message = 'point positions must strictly increase'
            raise ValueError(message)
        if np.any(np.abs(points_level) > 1.0):
            message = 'point levels must be between -1 and 1'
            raise ValueError(message)
        positions = np.arange(WAVE_TABLE_LENGTH) / WAVE_TABLE_LENGTH
        if shape == 'linear':
            table = np.interp(positions, points_at, points_level)
        elif shape == 'steps':
            table = points_level[np.searchsorted(points_at, positions, side='right') - 1]
        else:
            table = _monotone_cubic(positions, points_at, points_level)
        table -= table.mean()
        peak = float(np.max(np.abs(table)))
        if peak < FLAT_WAVE_TOLERANCE:
            message = 'the points have no variation: the wave is flat'
            raise ValueError(message)
        if normalize:
            table /= peak
        return cls._from_table(table)

    @override
    def __hash__(self) -> int:
        return hash(self._table.tobytes())

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Wave):
            return NotImplemented
        return self._table.tobytes() == other.table().tobytes()

    @override
    def __repr__(self) -> str:
        label = self._built_in_name if self._built_in_name is not None else 'custom'
        return f'Wave({label!r})'


class WaveRegistry:
    """Named custom waves; built-in names are reserved."""

    def __init__(self) -> None:
        """Start empty."""
        self._waves: dict[str, Wave] = {}

    def register(self, name: str, wave: Wave) -> None:
        """Register a wave under a name.

        Args:
            name: The name; registering it again replaces the earlier wave.
            wave: The wave.

        Raises:
            ValueError: If the name is empty or is a built-in wave name.
        """
        if not name:
            message = 'a wave name cannot be empty'
            raise ValueError(message)
        if name in BUILT_IN_WAVE_NAMES:
            message = f'{name!r} is a built-in wave name and cannot be registered'
            raise ValueError(message)
        self._waves[name] = wave

    def __getitem__(self, name: str) -> Wave:
        """Look a wave up: a registered one, else a built-in.

        Args:
            name: The wave's name.

        Returns:
            The wave.

        Raises:
            KeyError: If the name is neither registered nor built in.
        """
        if name in self._waves:
            return self._waves[name]
        if name in BUILT_IN_WAVE_NAMES:
            return Wave(name)
        message = f'no wave named {name!r}'
        raise KeyError(message)

    def __contains__(self, name: object) -> bool:
        """Whether the name is registered or built in.

        Args:
            name: The name to look for.

        Returns:
            True if the name is registered or built in.
        """
        return name in self._waves or name in BUILT_IN_WAVE_NAMES

    def mix(self, **weights: float) -> Wave:
        """Mix registered and built-in waves by name, like ``Wave.mix``.

        Args:
            **weights: Wave name to weight.

        Returns:
            The mixed wave.
        """
        return Wave.mix_resolved(weights=weights, resolve=self.__getitem__)
