"""Fuzzed valid instruments never render NaN or infinity (AUD-RT-004)."""

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from glitchygames.audio.instrument import Filter, Instrument, Noise, PitchCurve, Source
from glitchygames.audio.pitch import Hz
from glitchygames.audio.render import render_sound
from glitchygames.audio.spec import EnvelopeSpec
from glitchygames.audio.waves import BUILT_IN_WAVE_NAMES
from tests.audio.render_specs import SAMPLE_RATE, spec_for

# Highest note times the largest upward offset stays under the 12 kHz supported pitch
LOWEST_PITCH_HZ = 20.0
HIGHEST_PITCH_HZ = 2000.0
HIGHEST_SEMITONES = 24.0
HIGHEST_CUTOFF_HZ = 0.45 * SAMPLE_RATE

stage_seconds = st.floats(min_value=0.0, max_value=0.05)
levels = st.floats(min_value=0.0, max_value=1.0)
pitches = st.floats(min_value=LOWEST_PITCH_HZ, max_value=HIGHEST_PITCH_HZ)
envelopes = st.builds(
    EnvelopeSpec,
    attack=stage_seconds,
    decay=stage_seconds,
    sustain=levels,
    release=stage_seconds,
    curve=st.sampled_from(['linear', 'exponential', 'steps(1)', 'steps(4)', 'steps(16)']),
)
filters = st.none() | st.builds(
    Filter,
    kind=st.sampled_from(['low_pass', 'high_pass']),
    cutoff=st.floats(min_value=20.0, max_value=HIGHEST_CUTOFF_HZ),
)
pitch_curves = st.none() | st.builds(
    PitchCurve,
    to=pitches.map(Hz),
    seconds=st.floats(min_value=0.001, max_value=0.2),
    easing=st.sampled_from(['linear', 'ease_in_quad', 'ease_out_cubic', 'ease_in_out_sine']),
)
noises = st.builds(
    lambda kind, level, seed, width_and_taps: Noise(
        kind, level=level, seed=seed, bits=width_and_taps[0], taps=width_and_taps[1]
    ),
    kind=st.sampled_from(['white', 'lfsr']),
    level=levels,
    seed=st.none() | st.integers(min_value=0, max_value=2**64 - 1),
    width_and_taps=st.sampled_from([(15, (14, 13)), (7, (6, 5))]),
)
wave_sources = st.builds(
    Source,
    content=st.sampled_from(BUILT_IN_WAVE_NAMES),
    level=levels,
    semitones=st.floats(min_value=-12.0, max_value=HIGHEST_SEMITONES),
    detune_cents=st.floats(min_value=-50.0, max_value=50.0),
    pitch_curve=pitch_curves,
    envelope=st.none() | envelopes,
    filter=filters,
)
sources = st.dictionaries(
    keys=st.sampled_from(['first', 'second', 'third', 'fourth']),
    values=wave_sources | noises,
    min_size=1,
    max_size=4,
)
instruments = st.builds(
    Instrument,
    sources=sources,
    envelope=envelopes,
    filter=filters,
    drive=st.floats(min_value=0.0, max_value=20.0),
    normalize=st.booleans(),
    hard_edges=st.booleans(),
    seed=st.none() | st.integers(min_value=0, max_value=2**64 - 1),
)
melodies = st.lists(
    st.tuples(pitches.map(Hz), st.floats(min_value=0.005, max_value=0.1)), min_size=1, max_size=4
)


@st.composite
def valid_specs(draw):
    """A spec from a fuzzed instrument played as a single pitch, a melody or a chord.

    Returns:
        The spec.
    """
    instrument = draw(instruments)
    how = draw(st.sampled_from(['pitch', 'notes', 'chord']))
    if how == 'notes':
        return spec_for(instrument, notes=draw(melodies))
    length = draw(st.floats(min_value=0.005, max_value=0.2))
    if how == 'chord':
        chord = draw(st.lists(pitches.map(Hz), min_size=1, max_size=4))
        return spec_for(instrument, chord=chord, length=length)
    return spec_for(instrument, pitch=Hz(draw(pitches)), length=length)


@settings(derandomize=True, max_examples=200)
@given(spec=valid_specs())
def test_fuzzed_valid_specs_never_produce_non_finite_output(spec):
    """Every valid spec renders finite samples within full scale."""
    rendered = render_sound(spec)
    assert np.all(np.isfinite(rendered.samples))
    assert np.max(np.abs(rendered.samples), initial=0.0) <= 1.0
    assert np.isfinite(rendered.peak)
