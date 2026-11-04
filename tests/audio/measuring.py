"""Measurements of rendered audio for the renderer's tests (feature spec §15 acceptance values).

Every helper reads only samples, never the spec that made them, so a test checks what is heard.
"""

import math

import numpy as np

SAMPLE_RATE = 44100
CENTS_PER_OCTAVE = 1200.0
# Ignore DC and the slowest wobbles when looking for a fundamental
LOWEST_MEASURED_HZ = 5.0
GOLDEN_RATIO_STEP = (math.sqrt(5.0) - 1.0) / 2.0
FUNDAMENTAL_SEARCH_STEPS = 80
ENVELOPE_TOLERANCE = 1e-3
SILENCE_THRESHOLD = 1.0 / 1024.0
MINIMUM_SILENCE_FRAMES = 64
# Two components closer than this (in hertz) to a harmonic count as that harmonic's leakage
HARMONIC_GUARD_HZ = 10.0
DECIBELS_PER_DECADE = 20.0


def blackman_harris(length):
    """The 4-term Blackman-Harris window (sidelobes below -92 dB).

    Reference: F. J. Harris, "On the Use of Windows for Harmonic Analysis with the Discrete
    Fourier Transform", Proc. IEEE 66(1), 1978 (the minimum 4-term coefficients).

    Returns:
        The window.
    """
    positions = 2.0 * math.pi * np.arange(length) / (length - 1)
    return (
        0.35875
        - 0.48829 * np.cos(positions)
        + 0.14128 * np.cos(2.0 * positions)
        - 0.01168 * np.cos(3.0 * positions)
    )


def _windowed_magnitude_at(windowed, frequency, sample_rate):
    """|DTFT| of windowed samples at one frequency (not limited to FFT bins).

    Returns:
        The magnitude.
    """
    phases = np.exp(-2j * math.pi * frequency * np.arange(len(windowed)) / sample_rate)
    return abs(np.dot(windowed, phases))


def measured_fundamental(samples, sample_rate):
    """The frequency of the strongest spectral peak, to a small fraction of a cent.

    The FFT gives the peak's bin; a golden-section search over the window's main lobe then finds
    where the windowed spectrum (evaluated at any frequency, not just bins) is highest. With
    Blackman-Harris sidelobes below -92 dB a single tone's estimate is exact to well under 0.01
    cents over one second.

    Returns:
        The frequency in hertz.
    """
    windowed = np.asarray(samples, dtype=np.float64) * blackman_harris(len(samples))
    magnitudes = np.abs(np.fft.rfft(windowed))
    frequencies = np.fft.rfftfreq(len(windowed), 1.0 / sample_rate)
    magnitudes[frequencies < LOWEST_MEASURED_HZ] = 0.0
    peak_bin = int(np.argmax(magnitudes))
    bin_width = sample_rate / len(windowed)
    low = frequencies[peak_bin] - bin_width
    high = frequencies[peak_bin] + bin_width
    for _ in range(FUNDAMENTAL_SEARCH_STEPS):
        lower_probe = high - GOLDEN_RATIO_STEP * (high - low)
        upper_probe = low + GOLDEN_RATIO_STEP * (high - low)
        if _windowed_magnitude_at(windowed, lower_probe, sample_rate) < _windowed_magnitude_at(
            windowed, upper_probe, sample_rate
        ):
            low = lower_probe
        else:
            high = upper_probe
    return (low + high) / 2.0


def cents_between(first_hz, second_hz):
    """The distance between two frequencies in cents (always >= 0).

    Returns:
        Cents.
    """
    return abs(CENTS_PER_OCTAVE * math.log2(first_hz / second_hz))


def amplitude_envelope(samples):
    """The magnitude of the analytic signal (Hilbert transform done with the FFT).

    Returns:
        One amplitude per sample.
    """
    count = len(samples)
    spectrum = np.fft.fft(samples)
    weights = np.zeros(count)
    weights[0] = 1.0
    if count % 2 == 0:
        weights[count // 2] = 1.0
        weights[1 : count // 2] = 2.0
    else:
        weights[1 : (count + 1) // 2] = 2.0
    return np.abs(np.fft.ifft(spectrum * weights))


def stage_boundaries_in_seconds(samples, sample_rate):
    """Where an ADSR envelope's attack, decay, sustain and release end, in seconds.

    The amplitude envelope is read from the analytic signal. Attack ends where it first reaches
    its peak, decay where it first comes down to the sustain level (the most common level),
    sustain where it last holds that level and release where it last rises above silence.

    Returns:
        [attack end, decay end, sustain end, release end].
    """
    envelope = amplitude_envelope(samples)
    peak = float(np.max(envelope))
    attack_end = int(np.argmax(envelope >= peak - ENVELOPE_TOLERANCE))
    levels, counts = np.unique(np.round(envelope, 3), return_counts=True)
    sustain = float(levels[np.argmax(counts)])
    after_attack = envelope[attack_end:]
    decay_end = attack_end + int(np.argmax(after_attack <= sustain + ENVELOPE_TOLERANCE))
    holding = np.nonzero(envelope >= sustain - ENVELOPE_TOLERANCE)[0]
    sustain_end = int(holding[-1]) + 1
    sounding = np.nonzero(envelope > ENVELOPE_TOLERANCE)[0]
    release_end = int(sounding[-1]) + 1
    return [frame / sample_rate for frame in (attack_end, decay_end, sustain_end, release_end)]


def onset_frames(samples):
    """Frames where sound starts after silence (or at the very start).

    An onset is a frame above 1/1024 whose previous 64 frames (as many as exist) are all at or
    below it.

    Returns:
        The onset frames, in order.
    """
    loud = np.abs(samples) > SILENCE_THRESHOLD
    onsets = []
    for frame in np.nonzero(loud)[0]:
        earlier = loud[max(0, frame - MINIMUM_SILENCE_FRAMES) : frame]
        if not earlier.any():
            onsets.append(int(frame))
    return onsets


def _spectrum(samples, sample_rate):
    windowed = np.asarray(samples, dtype=np.float64) * blackman_harris(len(samples))
    return np.abs(np.fft.rfft(windowed)), np.fft.rfftfreq(len(samples), 1.0 / sample_rate)


def _decibels(ratio):
    return DECIBELS_PER_DECADE * math.log10(ratio)


def spectrum_peak_db(samples, frequency, sample_rate=SAMPLE_RATE):
    """The spectrum's level near a frequency, in dB relative to its strongest component.

    Returns:
        dB (0 for the strongest component, negative below it).
    """
    magnitudes, frequencies = _spectrum(samples, sample_rate)
    near = np.abs(frequencies - frequency) <= HARMONIC_GUARD_HZ
    return _decibels(float(np.max(magnitudes[near])) / float(np.max(magnitudes)))


def alias_floor_db(samples, fundamental, sample_rate=SAMPLE_RATE):
    """The loudest component that is not a harmonic of the fundamental, in dB below it.

    Returns:
        dB relative to the fundamental (negative: below it).
    """
    magnitudes, frequencies = _spectrum(samples, sample_rate)
    is_alias = frequencies >= HARMONIC_GUARD_HZ
    harmonic = fundamental
    while harmonic < sample_rate / 2.0:
        is_alias &= np.abs(frequencies - harmonic) > HARMONIC_GUARD_HZ
        harmonic += fundamental
    fundamental_level = float(
        np.max(magnitudes[np.abs(frequencies - fundamental) <= HARMONIC_GUARD_HZ])
    )
    return _decibels(float(np.max(magnitudes[is_alias])) / fundamental_level)


def zero_crossing_frequencies(samples, sample_rate):
    """The instantaneous frequency measured between successive upward zero crossings.

    Each crossing is placed between its two samples by linear interpolation.

    Returns:
        (times, frequencies): each period's midpoint in seconds and 1 / period in hertz.
    """
    before = samples[:-1]
    after = samples[1:]
    rising = np.nonzero((before < 0.0) & (after >= 0.0))[0]
    crossings = (rising + before[rising] / (before[rising] - after[rising])) / sample_rate
    periods = np.diff(crossings)
    return (crossings[:-1] + crossings[1:]) / 2.0, 1.0 / periods
