"""Notes and chords inside one sound (AUD-TIME-003, AUD-FUNC-011)."""

import numpy as np

from glitchygames.audio.instrument import Instrument
from glitchygames.audio.render import render_sound
from glitchygames.audio.spec import EnvelopeSpec
from tests.audio.measuring import onset_frames, spectrum_peak_db
from tests.audio.render_specs import HELD_ENVELOPE, SAMPLE_RATE, notes_spec, spec_for


def test_note_onsets_land_on_exact_frames():
    """Each note starts at round(start * sample rate)."""
    samples = render_sound(notes_spec('C5:0.1 E5:0.1', hard_edges=True)).samples
    assert onset_frames(samples) == [0, round(0.1 * 44100)]


def test_onsets_after_rests_land_on_exact_frames():
    """A rest moves the next onset by its length, to the frame."""
    samples = render_sound(notes_spec('A4:0.03 _:0.017 A5:0.05 B5:0.0371', hard_edges=True)).samples
    assert onset_frames(samples) == [0, round(0.047 * SAMPLE_RATE), round(0.097 * SAMPLE_RATE)]


def test_a_sound_lasts_until_its_last_note_releases():
    """Length is the last note's end plus the release."""
    envelope = EnvelopeSpec(attack=0.0, decay=0.0, sustain=1.0, release=0.1)
    samples = render_sound(notes_spec('A4:0.2 C5:0.3', envelope=envelope)).samples
    assert len(samples) == round(0.2 * SAMPLE_RATE) + round(0.3 * SAMPLE_RATE) + round(
        0.1 * SAMPLE_RATE
    )


def test_a_chords_spectrum_holds_each_pitch():
    """Each pitch of a chord stands out in the spectrum."""
    instrument = Instrument(wave='sine', envelope=HELD_ENVELOPE)
    samples = render_sound(spec_for(instrument, chord=('C4', 'E4', 'G4'), length=1.0)).samples
    for frequency in (261.626, 329.628, 391.995):
        assert spectrum_peak_db(samples, frequency) > -3


def test_overlapping_release_tails_are_summed():
    """A note's release overlapping the next note adds to it rather than being cut.

    The sustain is low enough that the overlap never reaches full scale (no clipping).
    """
    envelope = EnvelopeSpec(attack=0.0, decay=0.0, sustain=0.4, release=0.05)
    together = render_sound(
        notes_spec('A4:0.1 A4:0.1', wave='sine', envelope=envelope, hard_edges=True)
    ).samples
    alone = render_sound(
        notes_spec('A4:0.1', wave='sine', envelope=envelope, hard_edges=True)
    ).samples
    second = render_sound(
        notes_spec('_:0.1 A4:0.1', wave='sine', envelope=envelope, hard_edges=True)
    ).samples
    padded = np.zeros(len(together))
    padded[: len(alone)] = alone
    np.testing.assert_allclose(together, padded + second, atol=1e-12)
