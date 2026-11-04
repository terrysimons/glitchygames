"""Pitch curves with easing (AUD-INST-008)."""

import numpy as np
import pytest

from glitchygames.audio.instrument import Instrument, PitchCurve, Source
from glitchygames.audio.pitch import Hz
from glitchygames.audio.render import render_sound
from glitchygames.effects.easing import get_easing
from tests.audio.measuring import cents_between, measured_fundamental, zero_crossing_frequencies
from tests.audio.render_specs import HELD_ENVELOPE, SAMPLE_RATE, spec_for

ONE_PERCENT = 0.01
MEASURED_POINTS = np.linspace(0.05, 0.95, 10)


def glide_spec(  # ruff: ignore[too-many-arguments] - a test helper; each keyword is a knob
    *, start_hz, end_hz, seconds, easing, length, wave='sine'
):
    """A source gliding from the note to ``end_hz``.

    Returns:
        The spec.
    """
    source = Source(wave, pitch_curve=PitchCurve(to=Hz(end_hz), seconds=seconds, easing=easing))
    instrument = Instrument(sources={'glide': source}, envelope=HELD_ENVELOPE, hard_edges=True)
    return spec_for(instrument, pitch=Hz(start_hz), length=length)


@pytest.mark.parametrize('easing', ['linear', 'ease_in_quad', 'ease_out_cubic'])
def test_pitch_curve_follows_its_easing_within_one_percent(easing):
    """At 10 points the measured pitch is within 1% of the eased curve."""
    samples = render_sound(
        glide_spec(start_hz=220.0, end_hz=880.0, seconds=1.0, easing=easing, length=1.0)
    ).samples
    times, frequencies = zero_crossing_frequencies(samples, SAMPLE_RATE)
    eased = get_easing(easing)
    for point in MEASURED_POINTS:
        expected = 220.0 + 660.0 * eased(float(point))
        measured = float(np.interp(point, times, frequencies))
        assert abs(measured - expected) <= ONE_PERCENT * expected, (point, measured, expected)


def test_the_pitch_holds_the_target_after_the_curve():
    """Once the curve's time is over the source stays at the target."""
    samples = render_sound(
        glide_spec(start_hz=440.0, end_hz=220.0, seconds=0.1, easing='linear', length=0.5)
    ).samples
    times, frequencies = zero_crossing_frequencies(samples, SAMPLE_RATE)
    held = frequencies[times > 0.15]
    np.testing.assert_allclose(held, 220.0, rtol=1e-3)


def test_a_curve_longer_than_the_note_is_cut_with_it():
    """A note ending mid-curve stops partway along the glide."""
    samples = render_sound(
        glide_spec(start_hz=200.0, end_hz=1200.0, seconds=1.0, easing='linear', length=0.5)
    ).samples
    assert len(samples) == round(0.5 * SAMPLE_RATE)
    times, frequencies = zero_crossing_frequencies(samples, SAMPLE_RATE)
    assert float(np.interp(0.45, times, frequencies)) == pytest.approx(650.0, rel=ONE_PERCENT)


def test_a_polyblep_wave_follows_the_curve_too():
    """A square (PolyBLEP) glides like a sine: its zero crossings follow the curve."""
    samples = render_sound(
        glide_spec(
            start_hz=220.0, end_hz=440.0, seconds=0.5, easing='linear', length=0.5, wave='square'
        )
    ).samples
    times, frequencies = zero_crossing_frequencies(samples, SAMPLE_RATE)
    assert float(np.interp(0.25, times, frequencies)) == pytest.approx(330.0, rel=ONE_PERCENT)


def test_a_curve_overshooting_below_zero_hertz_is_refused():
    """An easing that overshoots below 0 Hz is refused by the curve check."""
    spec = glide_spec(start_hz=2000.0, end_hz=8.0, seconds=0.1, easing='ease_out_back', length=0.1)
    with pytest.raises(ValueError, match='frequency'):
        render_sound(spec)


def test_a_detuned_source_keeps_its_offset_through_the_glide():
    """The curve's target is for the source's base pitch: +7 cents ends 7 cents above it."""
    source = Source('sine', detune_cents=7.0, pitch_curve=PitchCurve(to=Hz(440.0), seconds=0.1))
    instrument = Instrument(sources={'glide': source}, envelope=HELD_ENVELOPE, hard_edges=True)
    samples = render_sound(spec_for(instrument, pitch=Hz(220.0), length=1.1)).samples
    held = samples[round(0.1 * SAMPLE_RATE) :]
    measured = measured_fundamental(held, SAMPLE_RATE)
    assert cents_between(measured, 440.0) == pytest.approx(7.0, abs=0.05)
    assert measured > 440.0
    times, frequencies = zero_crossing_frequencies(samples, SAMPLE_RATE)
    start = float(np.interp(0.01, times, frequencies))
    expected_start = 220.0 * 2.0 ** (7.0 / 1200.0) + (440.0 - 220.0) * 2.0 ** (7.0 / 1200.0) * 0.1
    assert start == pytest.approx(expected_start, rel=ONE_PERCENT)
