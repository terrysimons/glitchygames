"""Layered sources (AUD-SRC-004): every layer is heard, at its own level and shaping."""

import numpy as np

from glitchygames.audio.instrument import Filter, Instrument, Source
from glitchygames.audio.pitch import Hz
from glitchygames.audio.render import render_sound
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
