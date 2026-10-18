"""Sound synthesis toolkit: numpy waveforms, envelopes, filters and mixing.

Every function works on mono float64 arrays in [-1.0, 1.0]. Conversion to 16-bit PCM happens
once, in to_pcm16() / to_sound(). Sample rates default to the running mixer's rate, resolved at
call time.
"""

from __future__ import annotations

import enum
import math

import numpy as np
import numpy.typing as npt
import pygame

from glitchygames.effects.easing import get_easing

FloatArray = npt.NDArray[np.float64]

# pygame's default mixer rate, which pygame.init() starts (BUGS.md #22)
DEFAULT_SAMPLE_RATE = 44100


class Waveform(enum.Enum):
    """Oscillator shapes."""

    SINE = 'sine'
    SQUARE = 'square'
    SAWTOOTH = 'sawtooth'
    TRIANGLE = 'triangle'
    NOISE = 'noise'


def mixer_sample_rate() -> int:
    """Return the mixer's sample rate, or 44100 when the mixer is not initialized.

    Returns:
        Samples per second.

    """
    settings = pygame.mixer.get_init()
    if settings is None:
        return DEFAULT_SAMPLE_RATE
    return int(settings[0])


def sample_count(duration: float, sample_rate: int) -> int:
    """Number of samples for a duration (rounded to the nearest sample).

    Returns:
        The sample count.

    """
    return round(duration * sample_rate)


def _resolve_sample_rate(sample_rate: int | None) -> int:
    return mixer_sample_rate() if sample_rate is None else sample_rate


def _validate_frequencies(frequencies: FloatArray, sample_rate: int) -> None:
    nyquist = sample_rate / 2
    if frequencies.size and (np.min(frequencies) < 0.0 or np.max(frequencies) > nyquist):
        message = (
            f'frequency must be within 0-{nyquist} Hz (Nyquist at {sample_rate} Hz), '
            f'got {np.min(frequencies)}-{np.max(frequencies)}'
        )
        raise ValueError(message)


def _polyblep(phases: FloatArray, increments: FloatArray) -> FloatArray:
    """PolyBLEP residual that removes a sawtooth-style discontinuity at phase 0.

    Reference: V. Välimäki and A. Huovilainen, "Antialiasing Oscillators in Subtractive
    Synthesis", IEEE Signal Processing Magazine, 2007.

    Returns:
        The correction to subtract from (sawtooth) or add to (square) the naive waveform.

    """
    correction = np.zeros_like(phases)
    after_edge = (phases < increments) & (increments > 0.0)
    fraction = phases[after_edge] / increments[after_edge]
    correction[after_edge] = fraction + fraction - fraction * fraction - 1.0
    before_edge = (phases > 1.0 - increments) & (increments > 0.0)
    fraction = (phases[before_edge] - 1.0) / increments[before_edge]
    correction[before_edge] = fraction * fraction + fraction + fraction + 1.0
    return correction


def oscillator(  # ruff: ignore[too-many-arguments] - mirrors the spec's signature
    waveform: Waveform,
    frequency: float | FloatArray,
    duration: float,
    *,
    sample_rate: int | None = None,
    duty: float = 0.5,
    phase: float = 0.0,
    random_source: np.random.Generator | None = None,
) -> tuple[FloatArray, float]:
    """Generate a waveform.

    Sample i has phase `phase + sum(frequency[k] / sample_rate for k < i)` (an exclusive
    running sum), so sample 0 sits at `phase` and any pitch curve plays without clicks.

    Args:
        waveform: The shape.
        frequency: Hz, a number or one value per sample (ignored by NOISE).
        duration: Seconds (> 0). With a frequency array, must round to its length.
        sample_rate: Defaults to the mixer's rate.
        duty: SQUARE high fraction (0 < duty < 1).
        phase: Starting phase in cycles.
        random_source: numpy Generator for NOISE.

    Returns:
        (samples, end_phase) with end_phase wrapped to [0, 1) for seamless continuation.

    Raises:
        ValueError: On non-positive duration, a mismatched frequency array, a frequency
            outside 0-Nyquist, or duty outside (0, 1).

    """
    rate = _resolve_sample_rate(sample_rate)
    if duration <= 0.0:
        message = f'duration must be > 0, got {duration}'
        raise ValueError(message)
    if not 0.0 < duty < 1.0:
        message = f'duty must be between 0 and 1, got {duty}'
        raise ValueError(message)
    count = sample_count(duration, rate)
    if np.ndim(frequency) == 0:
        frequencies = np.full(count, float(frequency))
    else:
        frequencies = np.asarray(frequency, dtype=np.float64)
        if len(frequencies) != count:
            message = (
                f'frequency array length {len(frequencies)} does not match duration '
                f'{duration}s ({count} samples)'
            )
            raise ValueError(message)
    _validate_frequencies(frequencies, rate)

    if waveform is Waveform.NOISE:
        generator = random_source if random_source is not None else np.random.default_rng()
        return generator.uniform(-1.0, 1.0, count), phase % 1.0

    increments = frequencies / rate
    running = np.concatenate(([0.0], np.cumsum(increments[:-1])))
    phases = (phase + running) % 1.0
    end_phase = float((phase + increments.sum()) % 1.0)

    match waveform:
        case Waveform.SINE:
            samples = np.sin(2.0 * math.pi * phases)
        case Waveform.SAWTOOTH:
            samples = 2.0 * phases - 1.0 - _polyblep(phases, increments)
        case Waveform.SQUARE:
            samples = np.where(phases < duty, 1.0, -1.0)
            samples += _polyblep(phases, increments)
            samples -= _polyblep((phases + (1.0 - duty)) % 1.0, increments)
        case Waveform.TRIANGLE:
            # Naive: harmonics fall at 12 dB/octave, so aliasing stays negligible
            samples = 1.0 - 4.0 * np.abs(phases - 0.5)
    return samples, end_phase


def frequency_curve(
    start_hz: float,
    end_hz: float,
    duration: float,
    *,
    easing: str = 'linear',
    sample_rate: int | None = None,
) -> FloatArray:
    """Per-sample frequencies from start_hz to end_hz shaped by an easing curve.

    Sample i sits at time fraction i / (count - 1), so both endpoints are exact.

    Args:
        start_hz: First sample's frequency.
        end_hz: Last sample's frequency.
        duration: Seconds (> 0).
        easing: Name from glitchygames.effects.easing.
        sample_rate: Defaults to the mixer's rate.

    Returns:
        The frequency array.

    Raises:
        ValueError: On non-positive duration or if the eased curve leaves 0-Nyquist
            (overshooting easings such as ease_in_back).

    """
    rate = _resolve_sample_rate(sample_rate)
    if duration <= 0.0:
        message = f'duration must be > 0, got {duration}'
        raise ValueError(message)
    count = sample_count(duration, rate)
    fractions = np.linspace(0.0, 1.0, count) if count > 1 else np.zeros(count)
    easing_function = get_easing(easing)
    # The easing functions are scalar-only (math.*), so apply them element by element
    eased = np.array([easing_function(float(fraction)) for fraction in fractions])
    frequencies = start_hz + (end_hz - start_hz) * eased
    _validate_frequencies(frequencies, rate)
    return frequencies
