"""White and LFSR noise: seeds, periods, tap sets and clock rates (AUD-SRC-001)."""

import dataclasses

import numpy as np
import pytest

from glitchygames.audio.exceptions import SoundRenderError
from glitchygames.audio.instrument import Instrument, Noise, Source
from glitchygames.audio.pitch import Hz
from glitchygames.audio.render import lfsr_period, render_sound
from glitchygames.audio.spec import NoiseSpec
from tests.audio.render_specs import HELD_ENVELOPE, SAMPLE_RATE, noise_spec, spec_for


def test_lfsr_period_and_seeded_repeatability():
    """The same seed repeats; the 15-bit period is 32767; a non-maximal tap set is refused."""
    spec = noise_spec(kind='lfsr', bits=15, taps=(14, 13), rate_hz=44100.0, seed=7)
    assert np.array_equal(render_sound(spec).samples, render_sound(spec).samples)
    assert lfsr_period(bits=15, taps=(14, 13)) == 32767
    with pytest.raises(ValueError, match='maximal-length'):
        noise_spec(kind='lfsr', bits=15, taps=(14, 3))  # not a maximal-length tap set


def test_the_short_lfsr_period_is_127():
    """The 7-bit short mode repeats every 127 steps."""
    assert lfsr_period(bits=7, taps=(6, 5)) == 127


def test_an_lfsr_clocked_at_the_sample_rate_repeats_after_one_period():
    """Stepping once per sample, the output repeats exactly every 127 samples (7-bit)."""
    spec = noise_spec(kind='lfsr', bits=7, taps=(6, 5), rate_hz=44100.0, seed=3, length=0.05)
    samples = render_sound(spec).samples
    np.testing.assert_array_equal(samples[127:254], samples[:127])
    assert not np.array_equal(samples[1:128], samples[:127])
    assert set(np.unique(samples)) == {-1.0, 1.0}


def test_lfsr_period_refuses_tap_sets_outside_the_table():
    """Only the table's maximal-length tap sets are allowed."""
    with pytest.raises(ValueError, match='maximal-length'):
        lfsr_period(bits=7, taps=(6, 2))


def test_a_noise_spec_with_bad_taps_or_kind_is_refused():
    """NoiseSpec checks LFSR taps against its bit width, and its kind."""
    with pytest.raises(ValueError, match='maximal-length'):
        NoiseSpec(kind='lfsr', bits=7, taps=(14, 13), rate_hz=None, seed=None)
    with pytest.raises(ValueError, match='noise kind'):
        NoiseSpec(kind='pink', bits=15, taps=(14, 13), rate_hz=None, seed=None)


def test_white_noise_ignores_lfsr_settings():
    """White noise takes no taps, so its unused tap fields are not checked."""
    white = Noise('white', bits=7)
    assert white.taps == (14, 13)


def test_lfsr_seed_moves_the_start_in_the_sequence():
    """Two seeds give two different stretches of the same sequence."""
    first = render_sound(noise_spec(kind='lfsr', rate_hz=44100.0, seed=1)).samples
    second = render_sound(noise_spec(kind='lfsr', rate_hz=44100.0, seed=2)).samples
    assert not np.array_equal(first, second)


def test_an_lfsr_value_is_held_between_clock_steps():
    """At a quarter of the sample rate each value is held for four samples."""
    samples = render_sound(noise_spec(kind='lfsr', rate_hz=11025.0, seed=5)).samples
    changes = np.nonzero(np.diff(samples))[0] + 1
    assert changes.size > 100
    assert np.all(changes % 4 == 0)


def test_an_lfsr_without_a_rate_is_clocked_at_the_note():
    """With no rate, the clock follows the note's pitch."""
    samples = render_sound(noise_spec(kind='lfsr', pitch=8820.0, seed=5)).samples
    changes = np.nonzero(np.diff(samples))[0] + 1
    assert changes.size > 100
    assert np.all(changes % 5 == 0)


def test_the_unpitched_scale_multiplies_a_given_rate():
    """An unpitched sound played an octave above A4 runs its LFSR clock twice as fast."""
    instrument = Instrument(
        noise=Noise('lfsr', rate=Hz(4410.0), seed=5), envelope=HELD_ENVELOPE, hard_edges=True
    )
    spec = spec_for(instrument, pitch=Hz(880.0), length=0.25)
    assert spec.unpitched_scale == pytest.approx(2.0)
    changes = np.nonzero(np.diff(render_sound(spec).samples))[0] + 1
    assert changes.size > 100
    assert np.all(changes % 5 == 0)


def test_an_lfsr_clock_faster_than_the_sample_rate_is_refused():
    """The clock steps at most once per sample."""
    spec = noise_spec(kind='lfsr', rate_hz=50000.0)
    with pytest.raises(ValueError, match='LFSR clock'):
        render_sound(spec)


def test_white_noise_is_seeded_and_within_full_scale():
    """White noise repeats for a seed, differs for another and stays within -1..1."""
    first = render_sound(noise_spec(kind='white', seed=11)).samples
    again = render_sound(noise_spec(kind='white', seed=11)).samples
    other = render_sound(noise_spec(kind='white', seed=12)).samples
    np.testing.assert_array_equal(first, again)
    assert not np.array_equal(first, other)
    assert np.max(np.abs(first)) <= 1.0
    assert np.std(first) > 0.4


def test_white_noise_without_its_own_seed_uses_the_sounds_seed():
    """The sound's seed (from its name) seeds noise that has none of its own."""
    first = render_sound(noise_spec(kind='white', name='hiss')).samples
    again = render_sound(noise_spec(kind='white', name='hiss')).samples
    other = render_sound(noise_spec(kind='white', name='crackle')).samples
    np.testing.assert_array_equal(first, again)
    assert not np.array_equal(first, other)


def test_two_noise_layers_with_one_seed_differ_by_their_index():
    """Each source's generator combines the seed with the source's index."""
    instrument = Instrument(
        sources={'left': Noise('white'), 'right': Noise('white')},
        envelope=HELD_ENVELOPE,
        seed=4,
    )
    spec = spec_for(instrument, length=0.1)
    left_source, right_source = spec.sources
    silent_right = (left_source, dataclasses.replace(right_source, level=0.0))
    silent_left = (dataclasses.replace(left_source, level=0.0), right_source)
    left = render_sound(dataclasses.replace(spec, sources=silent_right)).samples
    right = render_sound(dataclasses.replace(spec, sources=silent_left)).samples
    assert left.any()
    assert right.any()
    assert not np.array_equal(left, right)


def test_notes_of_noise_each_get_fresh_noise():
    """Two noise notes do not repeat the same stretch."""
    instrument = Instrument(noise=Noise('white'), envelope=HELD_ENVELOPE, hard_edges=True)
    samples = render_sound(spec_for(instrument, notes='A4:0.05 A4:0.05')).samples
    half = round(0.05 * SAMPLE_RATE)
    assert not np.array_equal(samples[:half], samples[half:])


def test_an_unpitched_sound_without_notes_lasts_its_envelope():
    """With no pitch or length, noise plays for attack + decay, then its release."""
    instrument = Instrument(noise='white', envelope='percussive')
    spec = spec_for(instrument)
    assert spec.notes is None
    samples = render_sound(spec).samples
    assert len(samples) == round(0.001 * SAMPLE_RATE) + round(0.2 * SAMPLE_RATE) + round(
        0.02 * SAMPLE_RATE
    )


def test_a_pitched_sound_without_notes_names_the_sound():
    """A pitched instrument needs a pitch, notes or chord to render."""
    spec = spec_for(Instrument(wave='sine'), name='beep')
    with pytest.raises(SoundRenderError, match="'beep' needs a pitch, notes or chord"):
        render_sound(spec)


def test_a_mixed_wave_and_noise_instrument_is_pitched():
    """One wave layer makes the instrument pitched, so it too needs a pitch."""
    instrument = Instrument(sources={'tone': Source('sine'), 'hiss': Noise('white')})
    with pytest.raises(SoundRenderError, match='needs a pitch'):
        render_sound(spec_for(instrument, name='mixed'))
