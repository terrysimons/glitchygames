"""Envelopes: stage times (AUD-INST-001), curves and stepped levels (AUD-RETRO-003)."""

import numpy as np
import pytest

from glitchygames.audio.instrument import Instrument, Source
from glitchygames.audio.pitch import Hz
from glitchygames.audio.render import envelope_levels, render_sound
from glitchygames.audio.spec import EnvelopeSpec
from tests.audio.measuring import stage_boundaries_in_seconds
from tests.audio.render_specs import HELD_ENVELOPE, SAMPLE_RATE, single_note_spec, spec_for

ONE_MILLISECOND = 0.001


def render_envelope_only(envelope, *, length):
    """The envelope's levels for a note held ``length`` seconds.

    Returns:
        One level per frame, release included.
    """
    return envelope_levels(
        envelope, gate_frames=round(length * SAMPLE_RATE), sample_rate=SAMPLE_RATE
    )


def test_adsr_stage_times_are_within_a_millisecond():
    """Measured attack, decay, sustain and release ends are within 1 ms."""
    samples = render_sound(
        single_note_spec(
            wave='sine', hz=440.0, envelope=EnvelopeSpec(0.05, 0.1, 0.5, 0.2, 'linear'), length=0.5
        )
    ).samples
    assert stage_boundaries_in_seconds(samples, SAMPLE_RATE) == pytest.approx(
        [0.05, 0.15, 0.5, 0.7], abs=ONE_MILLISECOND
    )


def test_stepped_envelope_has_exactly_n_levels():
    """steps(16) quantizes the envelope to 16 levels above silence."""
    envelope = render_envelope_only(EnvelopeSpec(0.1, 0.1, 0.5, 0.1, 'steps(16)'), length=0.3)
    assert len(np.unique(np.round(envelope, 9))) <= 16 + 1


def test_stepped_levels_are_multiples_of_one_step():
    """Every stepped level is a whole number of 1/n steps, and the attack climbs through all."""
    envelope = render_envelope_only(EnvelopeSpec(0.1, 0.1, 0.5, 0.1, 'steps(4)'), length=0.3)
    np.testing.assert_allclose(envelope * 4.0, np.round(envelope * 4.0), atol=1e-12)
    assert set(np.round(envelope * 4.0)) == {0.0, 1.0, 2.0, 3.0, 4.0}


def test_steps_of_zero_is_refused():
    """steps(0) has no levels to step through."""
    with pytest.raises(ValueError, match='steps'):
        render_envelope_only(EnvelopeSpec(0.1, 0.1, 0.5, 0.1, 'steps(0)'), length=0.3)


def test_linear_stages_land_on_their_targets_at_their_frames():
    """Linear stages start at 0, peak at the attack's end and hold the sustain level."""
    envelope = render_envelope_only(EnvelopeSpec(0.01, 0.02, 0.25, 0.01), length=0.05)
    assert len(envelope) == round(0.06 * SAMPLE_RATE)
    assert envelope[0] == 0.0
    assert envelope[441] == pytest.approx(1.0)
    assert envelope[441 + 882] == pytest.approx(0.25)
    assert envelope[round(0.05 * SAMPLE_RATE) - 1] == pytest.approx(0.25)
    assert envelope[-1] == pytest.approx(0.25 / 441)


def test_exponential_stages_reach_their_targets_exactly_and_move_faster_early():
    """Exponential stages end on their targets (no step into the next stage) and lead linear."""
    exponential = render_envelope_only(
        EnvelopeSpec(0.01, 0.02, 0.25, 0.02, 'exponential'), length=0.05
    )
    linear = render_envelope_only(EnvelopeSpec(0.01, 0.02, 0.25, 0.02, 'linear'), length=0.05)
    attack_end = 441
    decay_end = attack_end + 882
    assert exponential[attack_end] == pytest.approx(1.0)
    assert exponential[decay_end] == pytest.approx(0.25)
    # Halfway through, the attack has risen further than a straight line and the decay fallen
    # further
    assert exponential[attack_end // 2] > linear[attack_end // 2] + 0.2
    assert exponential[attack_end + 441] < linear[attack_end + 441] - 0.1
    assert np.all(np.diff(exponential[: attack_end + 1]) > 0.0)
    assert np.all(np.diff(exponential[attack_end : decay_end + 1]) < 0.0)


def test_exponential_curve_covers_99_percent_of_a_stage_by_its_time_constant():
    """At the point a pure 99%-in-the-stage-time exponential would be, the curve is close."""
    exponential = render_envelope_only(EnvelopeSpec(0.1, 0.0, 1.0, 0.0, 'exponential'), length=0.1)
    # A time constant of stage / ln(100): one time constant in, a pure exponential is at 1 - 1/e
    one_time_constant = round(0.1 * SAMPLE_RATE / np.log(100.0))
    assert exponential[one_time_constant] == pytest.approx(1.0 - np.exp(-1.0), abs=0.01)


def test_release_starts_from_the_level_the_note_was_cut_at():
    """A note shorter than its attack releases from where the attack had got to."""
    envelope = render_envelope_only(EnvelopeSpec(0.1, 0.0, 1.0, 0.01), length=0.05)
    cut = round(0.05 * SAMPLE_RATE)
    assert envelope[cut - 1] == pytest.approx(0.5, abs=1e-3)
    assert envelope[cut] == pytest.approx(envelope[cut - 1], abs=1e-3)
    assert len(envelope) == cut + 441
    assert np.all(np.diff(envelope[cut:]) < 0.0)


def test_zero_length_stages_jump_straight_to_the_held_level():
    """With no attack or decay the held level starts at the first frame."""
    envelope = render_envelope_only(EnvelopeSpec(0.0, 0.0, 0.6, 0.0), length=0.01)
    np.testing.assert_allclose(envelope, 0.6)
    assert len(envelope) == 441


def test_a_source_envelope_shapes_only_its_source():
    """A layer with its own short envelope is silent once that envelope has ended."""
    short = EnvelopeSpec(attack=0.0, decay=0.05, sustain=0.0, release=0.0)
    instrument = Instrument(
        sources={'blip': Source('sine', envelope=short)}, envelope=HELD_ENVELOPE, hard_edges=True
    )
    samples = render_sound(spec_for(instrument, pitch=Hz(440.0), length=0.2)).samples
    assert np.max(np.abs(samples[: round(0.01 * SAMPLE_RATE)])) > 0.5
    assert not samples[round(0.05 * SAMPLE_RATE) :].any()
