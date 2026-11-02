"""Filters, drive (AUD-INST-007), de-clicking, level, clipping and the finite-output check."""

import logging

import numpy as np
import pytest

from glitchygames.audio.exceptions import GlitchyGamesAudioError, SoundRenderError
from glitchygames.audio.instrument import Filter, Instrument, Noise
from glitchygames.audio.render import RenderedSound, render_sound
from glitchygames.audio.spec import EnvelopeSpec
from tests.audio.measuring import measured_fundamental, spectrum_peak_db
from tests.audio.render_specs import SAMPLE_RATE, single_note_spec, spec_for

MINUS_ONE_DBFS = 10.0 ** (-1.0 / 20.0)
DECLICK_THRESHOLD = 1.0 / 1024.0


def test_boundary_declick_applies_only_when_the_edge_is_loud():
    """A loud first or last sample is faded; hard edges keep the click."""
    loud_start = render_sound(single_note_spec(wave='square', hz=440.0)).samples
    assert abs(loud_start[0]) < 1 / 1024 and abs(loud_start[-1]) < 1 / 1024
    hard = render_sound(single_note_spec(wave='square', hz=440.0, hard_edges=True)).samples
    assert abs(hard[0]) > 0.5


def test_declick_fades_last_one_and_two_milliseconds():
    """The fade-in is 1 ms and the fade-out 2 ms; the middle is untouched."""
    faded = render_sound(single_note_spec(wave='square', hz=440.0)).samples
    hard = render_sound(single_note_spec(wave='square', hz=440.0, hard_edges=True)).samples
    fade_in = round(0.001 * SAMPLE_RATE)
    fade_out = round(0.002 * SAMPLE_RATE)
    np.testing.assert_array_equal(faded[fade_in:-fade_out], hard[fade_in:-fade_out])
    assert not np.array_equal(faded[:fade_in], hard[:fade_in])
    assert not np.array_equal(faded[-fade_out:], hard[-fade_out:])
    assert faded[fade_in - 1] == pytest.approx(hard[fade_in - 1] * (fade_in - 1) / fade_in)


def test_a_quiet_edge_is_left_alone():
    """A sine starting at zero and released to silence gets no fade."""
    envelope = EnvelopeSpec(attack=0.0, decay=0.0, sustain=1.0, release=0.05)
    quiet = render_sound(single_note_spec(wave='sine', hz=440.0, envelope=envelope)).samples
    hard = render_sound(
        single_note_spec(wave='sine', hz=440.0, envelope=envelope, hard_edges=True)
    ).samples
    np.testing.assert_array_equal(quiet, hard)


def test_a_sound_shorter_than_its_fades_is_faded_whole():
    """A two-millisecond sound still ends at silence."""
    samples = render_sound(single_note_spec(wave='square', hz=1000.0, length=0.0005)).samples
    assert len(samples) == round(0.0005 * SAMPLE_RATE)
    assert abs(samples[0]) < DECLICK_THRESHOLD
    assert abs(samples[-1]) < DECLICK_THRESHOLD


def test_peak_over_full_scale_is_clipped_and_reported(caplog):
    """A peak above full scale is clipped, reported and logged with the sound's name."""
    with caplog.at_level(logging.WARNING, logger='game.audio.render'):
        rendered = render_sound(
            single_note_spec(wave='square', hz=440.0, level=3.0, name='too-loud')
        )
    assert rendered.clipped and np.max(np.abs(rendered.samples)) <= 1.0
    assert rendered.peak > 2.5
    assert 'too-loud' in caplog.text


def test_a_sound_within_full_scale_reports_its_peak_unclipped():
    """Levels are the author's: nothing is normalized without asking."""
    rendered = render_sound(single_note_spec(wave='sine', hz=440.0, level=0.25))
    assert not rendered.clipped
    assert rendered.peak == pytest.approx(0.25, abs=1e-3)
    assert rendered.peak == pytest.approx(float(np.max(np.abs(rendered.samples))))


def test_normalize_scales_the_peak_to_minus_one_dbfs():
    """normalize=True sets the peak to -1 dBFS, up or down."""
    quiet = render_sound(single_note_spec(wave='sine', hz=440.0, level=0.1, normalize=True))
    loud = render_sound(single_note_spec(wave='saw', hz=440.0, level=3.0, normalize=True))
    for rendered in (quiet, loud):
        assert rendered.peak == pytest.approx(MINUS_ONE_DBFS)
        assert not rendered.clipped


def test_normalize_leaves_silence_silent():
    """A silent sound stays silent under normalize."""
    rendered = render_sound(single_note_spec(wave='sine', hz=440.0, level=0.0, normalize=True))
    assert rendered.peak == 0.0
    assert not rendered.samples.any()


def test_rendered_samples_are_read_only_float64():
    """The rendered buffer is shared by the cache, so it cannot be changed."""
    rendered = render_sound(single_note_spec(wave='sine', hz=440.0))
    assert isinstance(rendered, RenderedSound)
    assert rendered.samples.dtype == np.float64
    assert rendered.samples.ndim == 1
    with pytest.raises(ValueError, match='read-only'):
        rendered.samples[0] = 1.0


def test_non_finite_output_raises_a_render_error_naming_the_sound():
    """A buffer holding NaN is a render bug, reported with the sound's name."""
    spec = single_note_spec(wave='sine', hz=440.0, name='broken', level=float('nan'))
    with pytest.raises(SoundRenderError, match="'broken'") as raised:
        render_sound(spec)
    assert isinstance(raised.value, GlitchyGamesAudioError)


def test_an_instrument_low_pass_removes_high_content():
    """The instrument's low-pass removes a saw's upper harmonics."""
    plain = render_sound(single_note_spec(wave='saw', hz=500.0, length=1.0)).samples
    filtered = render_sound(
        single_note_spec(wave='saw', hz=500.0, length=1.0, filter=Filter('low_pass', 1200.0))
    ).samples
    assert spectrum_peak_db(plain, 5000.0) > -25
    assert spectrum_peak_db(filtered, 5000.0) < -60
    assert spectrum_peak_db(filtered, 500.0) == pytest.approx(0.0)


def test_an_instrument_high_pass_removes_the_fundamental():
    """The instrument's high-pass removes a saw's fundamental and keeps its upper harmonics."""
    filtered = render_sound(
        single_note_spec(wave='saw', hz=200.0, length=1.0, filter=Filter('high_pass', 2000.0))
    ).samples
    # The FIR's stopband is about 53 dB down; the loudest kept harmonic (2200 Hz) is 21 dB down
    assert spectrum_peak_db(filtered, 200.0) < -25
    assert spectrum_peak_db(filtered, 4000.0) > -10


def test_the_filter_adds_no_latency():
    """A filtered note is centred on the same frames as the unfiltered one."""
    plain = render_sound(single_note_spec(wave='sine', hz=300.0, hard_edges=True)).samples
    filtered = render_sound(
        single_note_spec(wave='sine', hz=300.0, hard_edges=True, filter=Filter('low_pass', 5000.0))
    ).samples
    assert len(filtered) == len(plain)
    middle = slice(1000, len(plain) - 1000)
    np.testing.assert_allclose(filtered[middle], plain[middle], atol=1e-2)


@pytest.mark.parametrize('drive', [1.5, 20.0])
def test_drive_output_is_finite_and_bounded(drive):
    """Drive gives finite output near full scale, adds no length and no latency."""
    plain = render_sound(single_note_spec(wave='saw', hz=440.0, hard_edges=True)).samples
    rendered = render_sound(single_note_spec(wave='saw', hz=440.0, hard_edges=True, drive=drive))
    assert np.all(np.isfinite(rendered.samples))
    assert rendered.peak <= 1.25
    assert len(rendered.samples) == len(plain)
    lags = np.arange(-20, 21)
    correlations = [np.dot(np.roll(rendered.samples, lag), plain) for lag in lags]
    assert lags[int(np.argmax(correlations))] == 0


def test_drive_keeps_the_pitch_and_adds_harmonics():
    """Driving a sine keeps its fundamental and adds odd harmonics."""
    clean = render_sound(single_note_spec(wave='sine', hz=440.0, length=1.0)).samples
    driven = render_sound(single_note_spec(wave='sine', hz=440.0, length=1.0, drive=8.0)).samples
    assert measured_fundamental(driven, SAMPLE_RATE) == pytest.approx(440.0, abs=0.01)
    assert spectrum_peak_db(clean, 1320.0) < -90
    assert spectrum_peak_db(driven, 1320.0) > -20


def test_an_empty_sound_renders_no_samples():
    """An unpitched sound whose envelope has no length renders nothing, without failing."""
    instrument = Instrument(noise=Noise('white'), envelope=EnvelopeSpec(0.0, 0.0, 1.0, 0.0))
    rendered = render_sound(spec_for(instrument))
    assert len(rendered.samples) == 0
    assert rendered.peak == 0.0
    assert not rendered.clipped


def test_a_filter_at_or_above_nyquist_is_refused():
    """A FIR cutoff must sit below Nyquist."""
    spec = single_note_spec(wave='sine', hz=440.0, filter=Filter('low_pass', 30000.0))
    with pytest.raises(ValueError, match='cutoff'):
        render_sound(spec)


def test_a_source_level_scales_noise_too():
    """A noise layer's level scales it like any other."""
    instrument = Instrument(
        noise=Noise('white', level=0.25, seed=1), envelope=EnvelopeSpec(0.0, 0.0, 1.0, 0.0)
    )
    rendered = render_sound(spec_for(instrument, length=0.1))
    assert 0.2 < rendered.peak <= 0.25
