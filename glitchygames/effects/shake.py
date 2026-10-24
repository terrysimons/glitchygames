"""Stackable screen shake with optional controller rumble levels.

Pure math: no display or controller code. Camera2D applies a ScreenShake to world sprites;
SceneManager applies another to the whole presented frame.

The NOISE style follows the trauma model from Squirrel Eiserloh, "Juicing Your Cameras With
Math", GDC 2016: the visible magnitude scales with the square of the remaining shake, so big
hits feel much heavier than small ones and every shake eases out smoothly.
"""

from __future__ import annotations

import dataclasses
import enum
import math
from typing import TYPE_CHECKING, assert_never

from glitchygames.randomness import random_stream

if TYPE_CHECKING:
    import random

DEFAULT_MAXIMUM_OFFSET = 32.0
# The engine random stream shakes draw from (glitchygames/randomness.py)
SHAKE_RANDOM_STREAM = 'shake'
# BOUNCE amplitude remaining at the end of its duration (1% of strength)
BOUNCE_FINAL_AMPLITUDE_FRACTION = 0.01


class ShakeStyle(enum.Enum):
    """How a shake moves."""

    NOISE = 'noise'  # Smooth, heavy wobble (trauma model)
    JITTER = 'jitter'  # Random snap to a new offset every 1/frequency seconds
    BOUNCE = 'bounce'  # Damped spring that starts with a full-strength push


class ShakeTarget(enum.Flag):
    """What a shake moves. Combine with | to shake both."""

    WORLD = enum.auto()  # Camera-transformed sprites; HUD stays still
    SCREEN = enum.auto()  # The whole presented frame, including HUD and transitions


class ShakeAxis(enum.Enum):
    """Which axes a shake moves along."""

    BOTH = 'both'
    HORIZONTAL = 'horizontal'
    VERTICAL = 'vertical'


@dataclasses.dataclass(frozen=True)
class RumbleSettings:
    """Controller motor intensities (0.0-1.0).

    By default they are reached at full shake strength (strength / maximum offset), so a small
    on-screen shake rumbles gently. With scale_with_strength=False the intensities are absolute
    and only the shake's decay envelope scales them.
    """

    low_frequency: float
    high_frequency: float
    scale_with_strength: bool = True

    def __post_init__(self) -> None:
        """Validate motor intensities.

        Raises:
            ValueError: If either intensity is outside 0.0-1.0.

        """
        for field_name in ('low_frequency', 'high_frequency'):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                message = f'{field_name} must be between 0.0 and 1.0, got {value}'
                raise ValueError(message)


@dataclasses.dataclass(frozen=True)
class Shake:
    """One shake's settings."""

    style: ShakeStyle
    strength: float  # Peak offset in pixels
    duration: float  # Seconds
    frequency: float  # Hz
    axis: ShakeAxis = ShakeAxis.BOTH
    rumble: RumbleSettings | None = None

    def __post_init__(self) -> None:
        """Validate the settings.

        Raises:
            ValueError: If strength is negative or duration/frequency are not positive.

        """
        if self.strength < 0.0:
            message = f'strength must be >= 0, got {self.strength}'
            raise ValueError(message)
        if self.duration <= 0.0:
            message = f'duration must be > 0, got {self.duration}'
            raise ValueError(message)
        if self.frequency <= 0.0:
            message = f'frequency must be > 0, got {self.frequency}'
            raise ValueError(message)


class _ActiveShake:
    """One running shake: elapsed time plus the style's random state."""

    def __init__(self, *, shake: Shake, random_source: random.Random) -> None:
        self.shake = shake
        self.elapsed = 0.0
        self._random_source = random_source
        self._noise_lattice_horizontal: dict[int, float] = {}
        self._noise_lattice_vertical: dict[int, float] = {}
        self._jitter_step = -1
        self._jitter_horizontal = 0.0
        self._jitter_vertical = 0.0
        self._bounce_damping = -math.log(BOUNCE_FINAL_AMPLITUDE_FRACTION) / shake.duration

    @property
    def finished(self) -> bool:
        """True once elapsed time reaches the duration."""
        return self.elapsed >= self.shake.duration

    @property
    def remaining_time(self) -> float:
        """Seconds left, never negative."""
        return max(0.0, self.shake.duration - self.elapsed)

    def decay(self) -> float:
        """Envelope multiplier for offset and rumble.

        Only asked of a running shake: ScreenShake.update drops finished ones, and a new one
        has a positive duration still to run.

        Returns:
            The style's decay factor at the current elapsed time.

        """
        remaining_fraction = 1.0 - self.elapsed / self.shake.duration
        match self.shake.style:
            case ShakeStyle.NOISE:
                return remaining_fraction**2
            case ShakeStyle.JITTER:
                return remaining_fraction
            case ShakeStyle.BOUNCE:
                return math.exp(-self._bounce_damping * self.elapsed)
            case _:  # pragma: no cover - every ShakeStyle is matched above
                assert_never(self.shake.style)

    def offset(self) -> tuple[float, float]:
        """Current offset in pixels before intensity and the cap.

        Only asked of a running shake (see ``decay``).

        Returns:
            The (horizontal, vertical) offset.

        """
        magnitude = self.shake.strength * self.decay()
        unit_horizontal, unit_vertical = self._unit_direction()
        horizontal = unit_horizontal * magnitude
        vertical = unit_vertical * magnitude
        match self.shake.axis:
            case ShakeAxis.HORIZONTAL:
                return (horizontal, 0.0)
            case ShakeAxis.VERTICAL:
                return (0.0, vertical)
            case ShakeAxis.BOTH:
                return (horizontal, vertical)
            case _:  # pragma: no cover - every ShakeAxis is matched above
                assert_never(self.shake.axis)

    def _unit_direction(self) -> tuple[float, float]:
        position = self.elapsed * self.shake.frequency
        match self.shake.style:
            case ShakeStyle.NOISE:
                return (
                    self._value_noise(lattice=self._noise_lattice_horizontal, position=position),
                    self._value_noise(lattice=self._noise_lattice_vertical, position=position),
                )
            case ShakeStyle.JITTER:
                step = math.floor(position)
                if step != self._jitter_step:
                    self._jitter_step = step
                    self._jitter_horizontal = self._random_source.uniform(-1.0, 1.0)
                    self._jitter_vertical = self._random_source.uniform(-1.0, 1.0)
                return (self._jitter_horizontal, self._jitter_vertical)
            case ShakeStyle.BOUNCE:
                wave = math.cos(2.0 * math.pi * position)
                return (wave, wave)
            case _:  # pragma: no cover - every ShakeStyle is matched above
                assert_never(self.shake.style)

    def _value_noise(self, *, lattice: dict[int, float], position: float) -> float:
        """Smooth 1D value noise in [-1, 1]: random lattice values, smoothstep between them.

        Returns:
            The interpolated noise value.

        """
        left = math.floor(position)
        fraction = position - left
        left_value = self._lattice_value(lattice=lattice, index=left)
        right_value = self._lattice_value(lattice=lattice, index=left + 1)
        smoothed = fraction * fraction * (3.0 - 2.0 * fraction)
        return left_value + (right_value - left_value) * smoothed

    def _lattice_value(self, *, lattice: dict[int, float], index: int) -> float:
        if index not in lattice:
            lattice[index] = self._random_source.uniform(-1.0, 1.0)
        return lattice[index]


class ScreenShake:
    """Sums any number of active shakes into one capped offset."""

    def __init__(
        self,
        *,
        maximum_offset: float = DEFAULT_MAXIMUM_OFFSET,
        intensity: float = 1.0,
        random_source: random.Random | None = None,
    ) -> None:
        """Initialize with no active shakes.

        Args:
            maximum_offset: Per-axis cap on the summed offset, in pixels (> 0).
            intensity: Player setting 0.0-1.0 multiplying every offset (0 disables).
            random_source: Randomness for NOISE and JITTER; seed it in tests. None (the
                default) draws from the engine's ``random_stream(SHAKE_RANDOM_STREAM)``,
                looked up when each shake starts so a ScreenShake created before the engine
                seeded still follows the run's seed.

        Raises:
            ValueError: If maximum_offset is not positive.

        """
        if maximum_offset <= 0.0:
            message = f'maximum_offset must be > 0, got {maximum_offset}'
            raise ValueError(message)
        self._maximum_offset = maximum_offset
        self._intensity = 1.0
        self.intensity = intensity
        self._random_source: random.Random | None = random_source
        self._active: list[_ActiveShake] = []

    @property
    def maximum_offset(self) -> float:
        """Per-axis cap on the summed offset, in pixels."""
        return self._maximum_offset

    @property
    def intensity(self) -> float:
        """Player setting 0.0-1.0 multiplying every offset."""
        return self._intensity

    @intensity.setter
    def intensity(self, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            message = f'intensity must be between 0.0 and 1.0, got {value}'
            raise ValueError(message)
        self._intensity = value

    @property
    def is_active(self) -> bool:
        """True while any shake is running."""
        return bool(self._active)

    def add(self, shake: Shake) -> None:
        """Start a shake; it stacks with any already running.

        Args:
            shake: The shake to start.

        """
        random_source = self._random_source
        if random_source is None:
            random_source = random_stream(SHAKE_RANDOM_STREAM)
        self._active.append(_ActiveShake(shake=shake, random_source=random_source))

    def update(self, dt: float) -> None:
        """Advance every shake by game time and drop finished ones.

        Args:
            dt: Seconds since the last update.

        """
        for active_shake in self._active:
            active_shake.elapsed += dt
        self._active = [shake for shake in self._active if not shake.finished]

    def clear(self) -> None:
        """Stop every shake immediately."""
        self._active.clear()

    @property
    def offset(self) -> tuple[float, float]:
        """Summed offset times intensity, each axis clamped to +/- maximum_offset."""
        if self._intensity <= 0.0 or not self._active:
            return (0.0, 0.0)
        offsets = [shake.offset() for shake in self._active]
        horizontal = sum(offset[0] for offset in offsets) * self._intensity
        vertical = sum(offset[1] for offset in offsets) * self._intensity
        limit = self._maximum_offset
        return (max(-limit, min(limit, horizontal)), max(-limit, min(limit, vertical)))

    @property
    def rumble_levels(self) -> tuple[float, float]:
        """Per-motor maximum over rumbling shakes of value x decay x strength fraction.

        The strength fraction is 1.0 for shakes whose rumble has scale_with_strength=False.
        """
        low = 0.0
        high = 0.0
        for active_shake in self._active:
            rumble = active_shake.shake.rumble
            if rumble is None:
                continue
            strength_fraction = (
                min(1.0, active_shake.shake.strength / self._maximum_offset)
                if rumble.scale_with_strength
                else 1.0
            )
            scale = active_shake.decay() * strength_fraction
            low = max(low, rumble.low_frequency * scale)
            high = max(high, rumble.high_frequency * scale)
        return (low, high)

    @property
    def rumble_remaining(self) -> float:
        """Longest remaining time among shakes that rumble (0.0 if none)."""
        return max(
            (shake.remaining_time for shake in self._active if shake.shake.rumble is not None),
            default=0.0,
        )
