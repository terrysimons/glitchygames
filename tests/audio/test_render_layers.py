"""Layered sources (AUD-SRC-004): every layer is heard, at its own level and shaping."""

import dataclasses
import warnings

import numpy as np
import pytest

from glitchygames.audio.instrument import Filter, Instrument, Noise, Source
from glitchygames.audio.pitch import Hz
from glitchygames.audio.render import _render_source, render_sound
from glitchygames.audio.spec import NoteEvent
from glitchygames.checks import MissingValueError
from tests.audio.measuring import spectrum_peak_db
from tests.audio.render_specs import HELD_ENVELOPE, layered_spec, spec_for


def test_every_source_of_a_layer_is_present():
    """Each of three layers' pitches stands out in the spectrum."""
    samples = render_sound(layered_spec(hz=(110.0, 330.0, 990.0))).samples
    assert all(spectrum_peak_db(samples, frequency) > -30 for frequency in (110.0, 330.0, 990.0))


def test_a_layers_level_sets_its_loudness():
    """A layer at a quarter of another's level is 12 dB quieter."""
    instrument = Instrument(
        sources={
            'loud': Source('sine', level=0.8, pitch=Hz(200.0)),
            'quiet': Source('sine', level=0.2, pitch=Hz(700.0)),
        },
        envelope=HELD_ENVELOPE,
    )
    samples = render_sound(spec_for(instrument, pitch=Hz(200.0), length=1.0)).samples
    assert abs(spectrum_peak_db(samples, 700.0) - 20 * np.log10(0.25)) < 0.1


def test_a_layers_filter_shapes_only_that_layer():
    """A low-pass on one layer removes its high pitch and leaves the other layer alone."""
    instrument = Instrument(
        sources={
            'bass': Source('sine', level=0.5, pitch=Hz(200.0)),
            'muffled': Source(
                'sine', level=0.5, pitch=Hz(8000.0), filter=Filter('low_pass', 1000.0)
            ),
        },
        envelope=HELD_ENVELOPE,
    )
    samples = render_sound(spec_for(instrument, pitch=Hz(200.0), length=1.0)).samples
    assert spectrum_peak_db(samples, 200.0) > -0.1
    assert spectrum_peak_db(samples, 8000.0) < -40


def test_a_denormal_level_is_silence_not_non_finite():
    """A level below 1e-30 counts as silent, so normalizing never divides by a denormal."""
    instrument = Instrument(
        sources={'faint': Source('sine', level=2.2e-313, pitch=Hz(200.0))},
        envelope=HELD_ENVELOPE,
        normalize=True,
    )
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        samples = render_sound(spec_for(instrument, pitch=Hz(200.0), length=0.05)).samples
    assert np.all(samples == 0.0)


def test_a_denormal_noise_level_is_silence():
    """A noise source at a denormal level renders zeros."""
    instrument = Instrument(
        sources={'hiss': Noise('white', level=2.2e-313, seed=1)},
        envelope=HELD_ENVELOPE,
        normalize=True,
    )
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        samples = render_sound(spec_for(instrument, pitch=Hz(200.0), length=0.05)).samples
    assert np.all(samples == 0.0)


def test_a_noise_source_without_a_random_generator_raises_missing_value():
    """The render builds a generator for every noise source; one missing is a bug, said by name."""
    spec = spec_for(Instrument(noise='white', envelope=HELD_ENVELOPE), length=0.1)

    with pytest.raises(
        MissingValueError, match=r"^the noise source's random generator is missing$"
    ):
        _render_source(
            spec,
            spec.sources[0],
            NoteEvent(start_seconds=0.0, hz=440.0, length_seconds=0.1),
            gate_frames=100,
            frame_count=100,
            generator=None,
        )


def test_a_source_with_neither_wave_nor_noise_raises_missing_value():
    """A source is built with a wave or noise; one with neither is a bug, said by name."""
    spec = spec_for(Instrument(wave='sine', envelope=HELD_ENVELOPE), pitch=Hz(440.0), length=0.1)
    empty_source = dataclasses.replace(spec.sources[0], wave=None, noise=None)

    with pytest.raises(MissingValueError, match=r"^the source's wave is missing$"):
        _render_source(
            spec,
            empty_source,
            NoteEvent(start_seconds=0.0, hz=440.0, length_seconds=0.1),
            gate_frames=100,
            frame_count=100,
            generator=None,
        )
