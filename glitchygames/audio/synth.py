"""Sound synthesis toolkit: numpy waveforms, envelopes, filters and mixing.

Every function works on mono float64 arrays in [-1.0, 1.0]. Conversion to 16-bit PCM happens
once, in to_pcm16() / to_sound(). Sample rates default to the running mixer's rate, resolved at
call time.
"""

from __future__ import annotations

import dataclasses
import enum
import math
from typing import assert_never

import numpy as np
import numpy.typing as npt
import pygame

from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.effects.easing import get_easing
from glitchygames.randomness import numpy_stream

FloatArray = npt.NDArray[np.float64]

# pygame's default mixer rate, which pygame.init() starts (BUGS.md #22)
DEFAULT_SAMPLE_RATE = 44100
# The engine numpy stream NOISE draws from when no random_source is given, see randomness.py
SYNTH_RANDOM_STREAM = 'audio.synth'


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
    # Written as "not all within range" so NaN (every comparison False) is rejected too
    if frequencies.size and not np.all((frequencies >= 0.0) & (frequencies <= nyquist)):
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
        generator = (
            random_source if random_source is not None else numpy_stream(SYNTH_RANDOM_STREAM)
        )
        return generator.uniform(-1.0, 1.0, count), phase % 1.0

    increments = frequencies / rate
    # Exclusive running sum; unlike slicing off the last element, stays empty when count is 0
    running = np.cumsum(increments) - increments
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
        case _:  # pragma: no cover - every Waveform is matched above
            assert_never(waveform)
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


DEFAULT_FILTER_TAPS = 101
SIGNED_16_BIT_FORMAT = -16
PCM16_SCALE = 32767
MINIMUM_FILTER_TAPS = 3


@dataclasses.dataclass(frozen=True)
class Envelope:
    """Attack/decay/sustain/release amplitude envelope (seconds; sustain_level 0-1)."""

    attack: float
    decay: float
    sustain_level: float
    release: float


def apply_envelope(
    samples: FloatArray, envelope: Envelope, *, sample_rate: int | None = None
) -> FloatArray:
    """Shape samples with an envelope.

    Release is anchored to the end; attack and decay run from the start. When the stages
    are longer than the sound, release keeps its full length first, then attack, then decay.
    Ramps are linear and include both endpoints (attack starts at 0.0, release ends at 0.0).

    Returns:
        The shaped samples.

    """
    rate = _resolve_sample_rate(sample_rate)
    count = len(samples)
    release_count = min(sample_count(envelope.release, rate), count)
    attack_count = min(sample_count(envelope.attack, rate), count - release_count)
    decay_count = min(sample_count(envelope.decay, rate), count - release_count - attack_count)
    sustain_count = count - release_count - attack_count - decay_count

    # Each stage starts from the level the previous non-empty stage ended at (1.0 if none)
    attack_ramp = np.linspace(0.0, 1.0, attack_count)
    decay_ramp = np.linspace(1.0, envelope.sustain_level, decay_count)
    sustain = np.full(sustain_count, envelope.sustain_level)
    level_before_release = 1.0
    if sustain_count or decay_count:
        level_before_release = envelope.sustain_level
    release_ramp = np.linspace(level_before_release, 0.0, release_count)
    shape = np.concatenate((attack_ramp, decay_ramp, sustain, release_ramp))
    return samples * shape


def filter_kernel(cutoff_hz: float, *, sample_rate: int, taps: int, high_pass: bool) -> FloatArray:
    """Hamming-windowed sinc FIR kernel; high-pass by spectral inversion.

    Returns:
        The kernel (taps coefficients).

    Raises:
        ValueError: If taps is not an odd number >= 3 or cutoff is outside (0, Nyquist).

    """
    if taps < MINIMUM_FILTER_TAPS or taps % 2 == 0:
        message = f'taps must be an odd number >= 3, got {taps}'
        raise ValueError(message)
    if not 0.0 < cutoff_hz < sample_rate / 2:
        message = f'cutoff must be between 0 and {sample_rate / 2} Hz, got {cutoff_hz}'
        raise ValueError(message)
    normalized_cutoff = cutoff_hz / sample_rate
    positions = np.arange(taps) - (taps - 1) / 2
    kernel = 2 * normalized_cutoff * np.sinc(2 * normalized_cutoff * positions) * np.hamming(taps)
    kernel /= kernel.sum()
    if high_pass:
        kernel = -kernel
        kernel[(taps - 1) // 2] += 1.0
    return kernel


def apply_kernel(
    samples: FloatArray, kernel: FloatArray, *, history: FloatArray | None = None
) -> FloatArray:
    """Filter samples, continuing from `history` (the previous taps-1 input samples).

    Returns:
        Filtered samples, same length as the input.

    Raises:
        ValueError: If history has the wrong length.

    """
    history_length = len(kernel) - 1
    # np.convolve in 'valid' mode would otherwise return a few samples for empty input
    if len(samples) == 0:
        return np.zeros(0)
    if history is None:
        history = np.zeros(history_length)
    elif len(history) != history_length:
        message = f'history must have {history_length} samples, got {len(history)}'
        raise ValueError(message)
    return np.convolve(np.concatenate((history, samples)), kernel, mode='valid')


def low_pass(
    samples: FloatArray,
    cutoff_hz: float,
    *,
    sample_rate: int | None = None,
    taps: int = DEFAULT_FILTER_TAPS,
    history: FloatArray | None = None,
) -> FloatArray:
    """Remove content above cutoff_hz.

    Returns:
        Filtered samples, same length as the input.

    """
    rate = _resolve_sample_rate(sample_rate)
    kernel = filter_kernel(cutoff_hz, sample_rate=rate, taps=taps, high_pass=False)
    return apply_kernel(samples, kernel, history=history)


def high_pass(
    samples: FloatArray,
    cutoff_hz: float,
    *,
    sample_rate: int | None = None,
    taps: int = DEFAULT_FILTER_TAPS,
    history: FloatArray | None = None,
) -> FloatArray:
    """Remove content below cutoff_hz.

    Returns:
        Filtered samples, same length as the input.

    """
    rate = _resolve_sample_rate(sample_rate)
    kernel = filter_kernel(cutoff_hz, sample_rate=rate, taps=taps, high_pass=True)
    return apply_kernel(samples, kernel, history=history)


def distort(samples: FloatArray, drive: float) -> FloatArray:
    """Soft-clip with tanh; peaks at +/-1 stay at +/-1.

    Returns:
        Distorted samples.

    Raises:
        ValueError: If drive is not positive.

    """
    if drive <= 0.0:
        message = f'drive must be > 0, got {drive}'
        raise ValueError(message)
    return np.tanh(drive * samples) / math.tanh(drive)


def tremolo(
    samples: FloatArray,
    rate_hz: float,
    depth: float,
    *,
    sample_rate: int | None = None,
    phase: float = 0.0,
) -> tuple[FloatArray, float]:
    """Amplitude modulation: gain 1.0 at phase 0, (1 - depth) half a cycle later.

    Returns:
        (samples, end_phase) for seamless continuation.

    Raises:
        ValueError: If depth is outside 0-1 or rate_hz is not positive.

    """
    rate = _resolve_sample_rate(sample_rate)
    if not 0.0 <= depth <= 1.0:
        message = f'depth must be between 0.0 and 1.0, got {depth}'
        raise ValueError(message)
    if rate_hz <= 0.0:
        message = f'rate_hz must be > 0, got {rate_hz}'
        raise ValueError(message)
    phases = phase + np.arange(len(samples)) * rate_hz / rate
    gain = 1.0 - depth * (0.5 - 0.5 * np.cos(2 * math.pi * phases))
    end_phase = float((phase + len(samples) * rate_hz / rate) % 1.0)
    return samples * gain, end_phase


def mix(
    *layers: FloatArray | tuple[FloatArray, float], sample_rate: int | None = None
) -> FloatArray:
    """Sum layers, each optionally starting at an offset in seconds (>= 0).

    Returns:
        The mixed samples, long enough for the last layer to end (not normalized).

    Raises:
        ValueError: If an offset is negative.

    """
    rate = _resolve_sample_rate(sample_rate)
    placements: list[tuple[FloatArray, int]] = []
    for layer in layers:
        samples, offset = layer if isinstance(layer, tuple) else (layer, 0.0)
        if offset < 0.0:
            message = f'offset must be >= 0, got {offset}'
            raise ValueError(message)
        placements.append((samples, sample_count(offset, rate)))
    total = max((start + len(samples) for samples, start in placements), default=0)
    result = np.zeros(total)
    for samples, start in placements:
        result[start : start + len(samples)] += samples
    return result


def concatenate(*arrays: FloatArray) -> FloatArray:
    """Join arrays end to end.

    Returns:
        The joined samples.

    """
    return np.concatenate(arrays) if arrays else np.zeros(0)


def silence(duration: float, *, sample_rate: int | None = None) -> FloatArray:
    """Zeros for a duration (0 gives an empty array).

    Returns:
        The silent samples.

    """
    return np.zeros(sample_count(duration, _resolve_sample_rate(sample_rate)))


def normalize(samples: FloatArray, peak: float = 0.9) -> FloatArray:
    """Scale so the loudest sample is at peak; silence is returned unchanged.

    Returns:
        The scaled samples.

    Raises:
        ValueError: If peak is outside (0, 1].

    """
    if not 0.0 < peak <= 1.0:
        message = f'peak must be in (0, 1], got {peak}'
        raise ValueError(message)
    loudest = float(np.max(np.abs(samples))) if len(samples) else 0.0
    if loudest <= 0.0:
        return samples.copy()
    return samples * (peak / loudest)


def to_pcm16(samples: FloatArray) -> npt.NDArray[np.int16]:
    """Clip to [-1, 1], scale by 32767 and round to signed 16-bit.

    Returns:
        PCM samples.

    """
    return np.round(np.clip(samples, -1.0, 1.0) * PCM16_SCALE).astype(np.int16)


def to_sound(samples: FloatArray, *, volume: float = 0.5) -> pygame.mixer.Sound:
    """Turn mono samples into a pygame Sound matching the mixer.

    Returns:
        The sound, with its volume set.

    Raises:
        AudioUnavailableError: If the mixer is not initialized or is not signed 16-bit.

    """
    settings = pygame.mixer.get_init()
    if settings is None:
        message = 'pygame.mixer is not initialized'
        raise AudioUnavailableError(message)
    _rate, sample_format, channel_count = settings
    if sample_format != SIGNED_16_BIT_FORMAT:
        message = f'mixer format {sample_format} is not signed 16-bit'
        raise AudioUnavailableError(message)
    pcm = to_pcm16(samples)
    frames = pcm if channel_count == 1 else np.repeat(pcm[:, np.newaxis], channel_count, axis=1)
    frames = np.ascontiguousarray(frames)
    # pygame.sndarray.make_sound has incomplete type stubs for its ndarray parameter
    sound: pygame.mixer.Sound = pygame.sndarray.make_sound(frames)  # pyright: ignore[reportUnknownMemberType]
    sound.set_volume(volume)
    return sound
