"""The M1 renderer: a ``SoundSpec`` in, mono float64 samples out (impl spec 5).

``render_sound`` is pure: the same spec always gives the same samples, and it reads no mixer,
clock or engine random stream (noise is seeded from the spec, impl spec 6.3).

Each note is rendered on its own: every source renders its oscillator or noise for the note's
held length plus the amplifier's release, then its own filter, its own envelope and its level;
the sources are summed; then come the sound's filter, the amplifier envelope and drive. Notes
are summed at ``round(start_seconds * sample_rate)``. Then the sum must be finite, and last come
the boundary de-click fades, the optional normalization to -1 dBFS and the clip to full scale,
with the peak reported.

Filters and the 2x anti-alias kernel are applied centred (zero phase): a compiled sound is
rendered whole, so the kernels' delay is taken back and nothing is shifted in time.
"""

from __future__ import annotations

import functools
import logging
import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import numpy as np

from glitchygames.audio import synth
from glitchygames.audio.exceptions import SoundRenderError
from glitchygames.audio.instrument import UNPITCHED_REFERENCE_HZ
from glitchygames.audio.spec import NoteEvent, check_lfsr_taps
from glitchygames.audio.waves import LOWEST_BAND_HERTZ, WAVE_TABLE_LENGTH

if TYPE_CHECKING:
    from glitchygames.audio.spec import (
        EnvelopeSpec,
        FilterSpec,
        NoiseSpec,
        SoundSpec,
        SourceSpec,
    )
    from glitchygames.audio.waves import Wave

log: logging.Logger = logging.getLogger('game.audio.render')

FloatArray = synth.FloatArray

DECLICK_THRESHOLD: Final[float] = 1.0 / 1024.0
FADE_IN_SECONDS: Final[float] = 0.001
FADE_OUT_SECONDS: Final[float] = 0.002
FULL_SCALE: Final[float] = 1.0
NORMALIZED_PEAK: Final[float] = 10.0 ** (-1.0 / 20.0)  # -1 dBFS
# An exponential stage's time constant reaches 99% of the way to its target in the stage time
EXPONENTIAL_RATE: Final[float] = math.log(100.0)
STEPS_CURVE: Final[re.Pattern[str]] = re.compile(r'^steps\((\d+)\)$')
SEMITONES_PER_OCTAVE: Final[float] = 12.0
CENTS_PER_SEMITONE: Final[float] = 100.0
OVERSAMPLING: Final[int] = 2
# The 2x kernel passes up to 0.45 of the base rate and stops above its Nyquist
ANTI_ALIAS_CUTOFF_FRACTION: Final[float] = 0.45
ANTI_ALIAS_TAPS: Final[int] = 101
DRIVE_OVERSAMPLED_ABOVE: Final[float] = 2.0
# A PolyBLEP wave's first sample at phase 0: the square is high, the saw at its bottom
SAW_START_LEVEL: Final[float] = -1.0
SQUARE_START_LEVEL: Final[float] = 1.0


@dataclass(frozen=True, slots=True)
class RenderedSound:
    """A rendered sound.

    Attributes:
        samples: Mono float64 samples within -1..1 (read-only).
        peak: The loudest sample's magnitude before clipping.
        clipped: True when the peak was above full scale and the samples were clipped.
    """

    samples: FloatArray
    peak: float
    clipped: bool


def lfsr_period(*, bits: int, taps: tuple[int, int]) -> int:
    """How many steps an LFSR takes to come back to its first state.

    Args:
        bits: The register width.
        taps: The two tap bits, counted from 0.

    Taps that are not a maximal-length set from ``LFSR_MAXIMAL_TAPS`` raise ``ValueError``.

    Returns:
        The period, measured by running the register.
    """
    return len(_lfsr_sequence(bits, (taps[0], taps[1])))


@functools.cache
def _lfsr_sequence(bits: int, taps: tuple[int, int]) -> FloatArray:
    """One full period of a Galois LFSR's output bit, as -1/+1, starting from state 1.

    Reference: the Galois form in "Linear-feedback shift register", Wikipedia (shift right; when
    the bit shifted out is 1, XOR the tap mask, whose bit ``t - 1`` stands for tap ``t``).
    Taps that are not a maximal-length set from ``LFSR_MAXIMAL_TAPS`` raise ``ValueError``.

    Returns:
        A read-only array of 2^bits - 1 values.
    """
    check_lfsr_taps(bits, taps)
    mask = (1 << taps[0]) | (1 << taps[1])
    state = 1
    output_bits: list[int] = []
    while True:
        output_bit = state & 1
        output_bits.append(output_bit)
        state >>= 1
        if output_bit:
            state ^= mask
        if state == 1:
            break
    sequence = np.where(np.array(output_bits) == 1, 1.0, -1.0)
    sequence.setflags(write=False)
    return sequence


def _curve_shape(progress: FloatArray, curve: str) -> FloatArray:
    """How far along a stage the level is (0 at its start, 1 at its end).

    The exponential is the curve of a time constant that covers 99% of a stage in the stage's
    time (impl spec 5), rescaled so it lands exactly on the target at the stage's end and the
    next stage starts without a step. ``steps(n)`` is linear here and quantized afterwards.

    Returns:
        The fractions, 0-1.
    """
    if curve == 'exponential':
        return (1.0 - np.exp(-EXPONENTIAL_RATE * progress)) / (1.0 - math.exp(-EXPONENTIAL_RATE))
    return progress


def _step_count(curve: str) -> int | None:
    """The n of a ``steps(n)`` curve, or None for a smooth curve.

    Returns:
        n, or None.

    Raises:
        ValueError: On ``steps(0)``.
    """
    match = STEPS_CURVE.match(curve)
    if match is None:
        return None
    steps = int(match.group(1))
    if steps < 1:
        message = f'an envelope needs at least one step, got {curve!r}'
        raise ValueError(message)
    return steps


def envelope_levels(envelope: EnvelopeSpec, *, gate_frames: int, sample_rate: int) -> FloatArray:
    """An envelope's level at each frame of a note held ``gate_frames`` frames.

    Attack runs from 0 to 1, decay from 1 to the sustain level, which holds until the gate ends;
    the release then runs to 0 from whatever level the gate ended at, so a note cut short in its
    attack releases from there without a jump.

    Args:
        envelope: The envelope.
        gate_frames: How many frames the note is held before its release.
        sample_rate: Samples per second.

    Returns:
        ``gate_frames`` plus the release's frames of levels.
    """
    steps = _step_count(envelope.curve)
    attack = round(envelope.attack * sample_rate)
    decay = round(envelope.decay * sample_rate)
    release = round(envelope.release * sample_rate)
    # One frame past the gate: the level the release starts from
    frames = np.arange(gate_frames + 1, dtype=np.float64)
    held = np.full(gate_frames + 1, envelope.sustain)
    if attack:
        in_attack = frames < attack
        held[in_attack] = _curve_shape(frames[in_attack] / attack, envelope.curve)
    if decay:
        in_decay = (frames >= attack) & (frames < attack + decay)
        shape = _curve_shape((frames[in_decay] - attack) / decay, envelope.curve)
        held[in_decay] = 1.0 + (envelope.sustain - 1.0) * shape
    release_start = held[gate_frames]
    released = release_start * (
        1.0 - _curve_shape(np.arange(release, dtype=np.float64) / max(release, 1), envelope.curve)
    )
    levels = np.concatenate((held[:gate_frames], released))
    if steps is not None:
        levels = np.round(levels * steps) / steps
    return levels


def _check_frequencies(frequencies: FloatArray, sample_rate: int) -> None:
    nyquist = sample_rate / 2.0
    # Written as "not all within range" so NaN is refused too
    if not np.all((frequencies >= 0.0) & (frequencies <= nyquist)):
        message = (
            f'frequency must be within 0-{nyquist} Hz (Nyquist at {sample_rate} Hz), '
            f'got {np.min(frequencies)}-{np.max(frequencies)}'
        )
        raise ValueError(message)


def _tuning_ratio(source: SourceSpec) -> float:
    semitones = source.semitones + source.detune_cents / CENTS_PER_SEMITONE
    return 2.0 ** (semitones / SEMITONES_PER_OCTAVE)


def _source_frequencies(
    source: SourceSpec, event: NoteEvent, *, frame_count: int, sample_rate: int
) -> FloatArray:
    """The source's frequency at each frame: its pitch, then its glide, if it has one.

    Returns:
        One frequency per frame, in hertz.
    """
    start_hz = (source.fixed_hz if source.fixed_hz is not None else event.hz) * _tuning_ratio(
        source
    )
    frequencies = np.full(frame_count, start_hz)
    curve = source.pitch_curve
    if curve is not None:
        glide = synth.frequency_curve(
            start_hz, curve.target_hz, curve.seconds, easing=curve.easing, sample_rate=sample_rate
        )
        gliding = min(len(glide), frame_count)
        frequencies[:gliding] = glide[:gliding]
        frequencies[gliding:] = curve.target_hz
    return frequencies


@functools.cache
def _anti_alias_kernel(sample_rate: int) -> FloatArray:
    """The low-pass kernel at twice ``sample_rate`` that 2x oversampling filters with.

    Returns:
        A read-only kernel.
    """
    kernel = synth.filter_kernel(
        ANTI_ALIAS_CUTOFF_FRACTION * sample_rate,
        sample_rate=OVERSAMPLING * sample_rate,
        taps=ANTI_ALIAS_TAPS,
        high_pass=False,
    )
    kernel.setflags(write=False)
    return kernel


def _centered(samples: FloatArray, kernel: FloatArray) -> FloatArray:
    """Filter with a symmetric kernel, its (taps - 1) / 2 frame delay taken back.

    Returns:
        The filtered samples, as many as given.
    """
    half = (len(kernel) - 1) // 2
    return synth.apply_kernel(np.concatenate((samples, np.zeros(half))), kernel)[half:]


def _polyblep_samples(
    wave: Wave, frequencies: FloatArray, *, duty: float, sample_rate: int
) -> FloatArray:
    """A saw, square or pulse through ``synth.oscillator`` at 2x, then filtered and decimated.

    At 1x the PolyBLEP residual leaves aliases only 27 dB under a 3520 Hz fundamental (measured);
    AUD-WAVE-006 needs 40, which 2x reaches (51 dB). The oscillator runs half a kernel past the
    note so the filter sees the wave go on, not stop. The first sample keeps its naive level:
    PolyBLEP smooths the wrap from a previous cycle, and a note's first sample has none.

    Returns:
        One sample per frequency.
    """
    half = (ANTI_ALIAS_TAPS - 1) // 2
    oversampled_rate = OVERSAMPLING * sample_rate
    oversampled = np.concatenate((
        np.repeat(frequencies, OVERSAMPLING),
        np.full(half, frequencies[-1]),
    ))
    is_saw = wave.name == 'saw'
    samples, _end_phase = synth.oscillator(
        synth.Waveform.SAWTOOTH if is_saw else synth.Waveform.SQUARE,
        oversampled,
        len(oversampled) / oversampled_rate,
        sample_rate=oversampled_rate,
        duty=duty,
    )
    samples[0] = SAW_START_LEVEL if is_saw else SQUARE_START_LEVEL
    filtered = _centered(samples, _anti_alias_kernel(sample_rate))
    return filtered[: OVERSAMPLING * len(frequencies) : OVERSAMPLING]


def _table_samples(wave: Wave, frequencies: FloatArray, *, sample_rate: int) -> FloatArray:
    """Read the wave's mip table, linearly interpolated, phase restarting at 0.

    The table spans ``note_periods_per_cycle`` note periods, so it is read (and its band chosen)
    at the note frequency divided by that. A note under the lowest band, 0 Hz included (which
    ``band_limited_table`` refuses), reads the lowest band.

    Returns:
        One sample per frequency.
    """
    table_frequencies = frequencies / wave.note_periods_per_cycle
    highest = max(float(np.max(table_frequencies)), LOWEST_BAND_HERTZ)
    table = wave.band_limited_table(highest_frequency=highest, sample_rate=sample_rate)
    increments = table_frequencies / sample_rate
    # Exclusive running sum, as synth.oscillator: sample 0 sits at phase 0
    positions = ((np.cumsum(increments) - increments) % 1.0) * WAVE_TABLE_LENGTH
    below = np.floor(positions)
    fraction = positions - below
    below_index = below.astype(np.intp) % WAVE_TABLE_LENGTH
    above_index = (below_index + 1) % WAVE_TABLE_LENGTH
    return table[below_index] * (1.0 - fraction) + table[above_index] * fraction


def _noise_samples(
    noise: NoiseSpec,
    frequencies: FloatArray,
    *,
    generator: np.random.Generator,
    clock_scale: float,
    sample_rate: int,
) -> FloatArray:
    """White noise, or an LFSR's period gathered at its clock's step positions.

    The LFSR's clock is ``rate_hz`` times ``clock_scale`` (the unpitched scale and the source's
    tuning), or the note's frequency when it has no rate. Each note starts at a seeded point
    of the period.

    Returns:
        One sample per frequency.

    Raises:
        ValueError: If the LFSR clock is negative or steps more than once per sample.
    """
    count = len(frequencies)
    if noise.kind == 'white':
        return generator.uniform(-1.0, 1.0, count)
    sequence = _lfsr_sequence(noise.bits, noise.taps)
    clock = frequencies if noise.rate_hz is None else np.full(count, noise.rate_hz * clock_scale)
    if not np.all((clock >= 0.0) & (clock <= sample_rate)):
        message = f'LFSR clock must be within 0-{sample_rate} Hz, got {np.max(clock)}'
        raise ValueError(message)
    # Summed in hertz then divided, so a clock that divides the rate steps on exact frames
    steps = np.floor((np.cumsum(clock) - clock) / sample_rate).astype(np.int64)
    # numpy's stubs for Generator.integers name generic types basedpyright cannot resolve
    start = int(generator.integers(len(sequence)))  # pyright: ignore[reportUnknownMemberType]
    return sequence[(start + steps) % len(sequence)]


def _filtered(samples: FloatArray, filter_spec: FilterSpec, sample_rate: int) -> FloatArray:
    kernel = synth.filter_kernel(
        filter_spec.cutoff_hz,
        sample_rate=sample_rate,
        taps=synth.DEFAULT_FILTER_TAPS,
        high_pass=filter_spec.kind == 'high_pass',
    )
    return _centered(samples, kernel)


def _driven(samples: FloatArray, drive: float, sample_rate: int) -> FloatArray:
    """``synth.distort``; above drive 2 at 2x oversampling, so its harmonics do not alias.

    Returns:
        The driven samples, as many as given.
    """
    if drive <= 0.0:
        return samples
    if drive <= DRIVE_OVERSAMPLED_ABOVE:
        return synth.distort(samples, drive)
    kernel = _anti_alias_kernel(sample_rate)
    upsampled = np.zeros(OVERSAMPLING * len(samples))
    upsampled[::OVERSAMPLING] = samples
    # Zero-stuffing leaves 1/OVERSAMPLING of the level; the kernel's unity gain does not restore it
    upsampled = OVERSAMPLING * _centered(upsampled, kernel)
    return _centered(synth.distort(upsampled, drive), kernel)[::OVERSAMPLING]


def _fitted(levels: FloatArray, frame_count: int) -> FloatArray:
    """Levels cut or padded with silence to ``frame_count`` frames.

    Returns:
        Exactly ``frame_count`` levels.
    """
    fitted = np.zeros(frame_count)
    shared = min(len(levels), frame_count)
    fitted[:shared] = levels[:shared]
    return fitted


def _render_source(  # ruff: ignore[too-many-arguments] - one call site, each argument needed
    spec: SoundSpec,
    source: SourceSpec,
    event: NoteEvent,
    *,
    gate_frames: int,
    frame_count: int,
    generator: np.random.Generator | None,
) -> FloatArray:
    rate = spec.sample_rate
    frequencies = _source_frequencies(source, event, frame_count=frame_count, sample_rate=rate)
    if source.noise is not None:
        assert generator is not None
        layer = _noise_samples(
            source.noise,
            frequencies,
            generator=generator,
            clock_scale=spec.unpitched_scale * _tuning_ratio(source),
            sample_rate=rate,
        )
    else:
        wave = source.wave
        assert wave is not None  # a SourceSpec holds a wave or noise
        _check_frequencies(frequencies, rate)
        if wave.is_built_in_polyblep:
            layer = _polyblep_samples(wave, frequencies, duty=source.duty, sample_rate=rate)
        else:
            layer = _table_samples(wave, frequencies, sample_rate=rate)
    if source.filter is not None:
        layer = _filtered(layer, source.filter, rate)
    if source.envelope is not None:
        levels = envelope_levels(source.envelope, gate_frames=gate_frames, sample_rate=rate)
        layer *= _fitted(levels, frame_count)
    return source.level * layer


def _render_note(
    spec: SoundSpec,
    event: NoteEvent,
    *,
    gate_frames: int,
    generators: dict[int, np.random.Generator],
) -> FloatArray:
    """One note: its sources summed, then the sound's filter, amplifier envelope and drive.

    Returns:
        The note's samples: its held frames plus the amplifier's release.
    """
    rate = spec.sample_rate
    amplifier = envelope_levels(spec.envelope, gate_frames=gate_frames, sample_rate=rate)
    frame_count = len(amplifier)
    mixed = np.zeros(frame_count)
    if frame_count == 0:
        return mixed
    for index, source in enumerate(spec.sources):
        mixed += _render_source(
            spec,
            source,
            event,
            gate_frames=gate_frames,
            frame_count=frame_count,
            generator=generators.get(index),
        )
    if spec.filter is not None:
        mixed = _filtered(mixed, spec.filter, rate)
    return _driven(mixed * amplifier, spec.drive, rate)


def _note_events(spec: SoundSpec) -> tuple[NoteEvent, ...]:
    """The spec's notes; an unpitched sound without any is held for its attack and decay.

    Returns:
        The events.

    Raises:
        SoundRenderError: For a pitched sound without notes.
    """
    if spec.notes is not None:
        return spec.notes
    if not all(source.noise is not None for source in spec.sources):
        message = f'sound {spec.name!r} needs a pitch, notes or chord'
        raise SoundRenderError(message)
    rate = spec.sample_rate
    held_frames = round(spec.envelope.attack * rate) + round(spec.envelope.decay * rate)
    return (NoteEvent(0.0, UNPITCHED_REFERENCE_HZ, held_frames / rate),)


def _declicked(samples: FloatArray, sample_rate: int) -> FloatArray:
    """Fade in 1 ms when the first sample is loud, fade out 2 ms when the last one is (impl 5).

    Returns:
        A faded copy.
    """
    result = samples.copy()
    if len(result) and abs(result[0]) > DECLICK_THRESHOLD:
        fade = round(FADE_IN_SECONDS * sample_rate)
        shared = min(fade, len(result))
        result[:shared] *= np.arange(shared) / fade
    if len(result) and abs(result[-1]) > DECLICK_THRESHOLD:
        fade = round(FADE_OUT_SECONDS * sample_rate)
        shared = min(fade, len(result))
        result[-shared:] *= (np.arange(fade - 1, -1, -1) / fade)[-shared:]
    return result


def render_sound(spec: SoundSpec) -> RenderedSound:
    """Render a spec to mono float64 samples.

    An invalid value the spec could not check alone raises ``ValueError`` from the stage that
    meets it: a frequency outside 0-Nyquist, a filter cutoff at or above Nyquist, an LFSR clock
    above the sample rate or a ``steps(0)`` envelope.

    Args:
        spec: The sound.

    Returns:
        The samples (read-only, clipped to full scale), their peak and whether they clipped.

    Raises:
        SoundRenderError: For a pitched sound with no notes, or a render that is not finite.
    """
    rate = spec.sample_rate
    events = _note_events(spec)
    release_frames = round(spec.envelope.release * rate)
    placed = [
        (round(event.start_seconds * rate), round(event.length_seconds * rate), event)
        for event in events
    ]
    total = max((start + gate + release_frames for start, gate, _ in placed), default=0)
    # Per impl spec 6.3: each noise source's seed (its own, else the sound's) combined with its
    # index. default_rng of a list of ints is Generator(PCG64(SeedSequence(that list))), the
    # form the randomness guard (tests/test_unseeded_randomness_guard.py) reads as seeded
    generators = {
        index: np.random.default_rng([
            source.noise.seed if source.noise.seed is not None else spec.seed,
            index,
        ])
        for index, source in enumerate(spec.sources)
        if source.noise is not None
    }
    mixed = np.zeros(total)
    for start, gate, event in placed:
        note = _render_note(spec, event, gate_frames=gate, generators=generators)
        mixed[start : start + len(note)] += note
    if not np.all(np.isfinite(mixed)):
        message = f'sound {spec.name!r} rendered non-finite samples (NaN or infinity)'
        raise SoundRenderError(message)
    if not spec.hard_edges:
        mixed = _declicked(mixed, rate)
    if spec.normalize:
        mixed = synth.normalize(mixed, NORMALIZED_PEAK)
    peak = float(np.max(np.abs(mixed), initial=0.0))
    clipped = peak > FULL_SCALE
    if clipped:
        log.warning('Sound %r peaked at %.3f, above full scale: clipped', spec.name, peak)
        mixed = np.clip(mixed, -FULL_SCALE, FULL_SCALE)
    mixed.setflags(write=False)
    return RenderedSound(samples=mixed, peak=peak, clipped=clipped)
