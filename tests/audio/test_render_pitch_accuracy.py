"""Rendered pitch accuracy (AUD-PITCH-006) and how each source's frequency is worked out."""

import dataclasses

import numpy as np
import pytest

from glitchygames.audio.instrument import Instrument, Source
from glitchygames.audio.pitch import Hz
from glitchygames.audio.render import render_sound
from glitchygames.audio.waves import Harmonics, Wave
from tests.audio.measuring import cents_between, measured_fundamental
from tests.audio.render_specs import HELD_ENVELOPE, SAMPLE_RATE, single_note_spec, spec_for

HALF_A_CENT = 0.5


@pytest.mark.parametrize('wave', ['sine', 'square', 'saw', 'triangle'])
@pytest.mark.parametrize('frequency', [55.0, 440.0, 3520.0])
def test_measured_fundamental_is_within_half_a_cent(wave, frequency):
    """The measured fundamental is within half a cent of the asked pitch."""
    samples = render_sound(
        single_note_spec(wave=wave, hz=frequency, length=1.0, sustain=1.0)
    ).samples
    assert cents_between(measured_fundamental(samples, SAMPLE_RATE), frequency) <= HALF_A_CENT


@pytest.mark.parametrize('wave', ['pulse_12', 'pulse_75'])
def test_pulse_waves_play_at_their_pitch(wave):
    """Pulse waves (PolyBLEP with their duty) play at their pitch."""
    samples = render_sound(single_note_spec(wave=wave, hz=440.0, length=1.0)).samples
    assert cents_between(measured_fundamental(samples, SAMPLE_RATE), 440.0) <= HALF_A_CENT


def test_a_mixed_wave_reads_its_table_at_the_note_pitch():
    """A mixed (table) wave plays at the note's pitch."""
    mixed = Wave.mix(sine=0.7, triangle=0.3)
    samples = render_sound(single_note_spec(wave=mixed, hz=330.0, length=1.0)).samples
    assert cents_between(measured_fundamental(samples, SAMPLE_RATE), 330.0) <= HALF_A_CENT


def test_a_wave_spanning_two_note_periods_keeps_the_note_pitch():
    """A sub-octave wave's table spans two note periods; the note still sounds at its pitch.

    The sub-octave is quieter than the fundamental here, so the strongest peak is the note's.
    """
    organ = Wave.from_harmonics(Harmonics(sub_octave=0.3, fundamental=1.0))
    assert organ.note_periods_per_cycle == 2
    samples = render_sound(single_note_spec(wave=organ, hz=440.0, length=1.0)).samples
    assert cents_between(measured_fundamental(samples, SAMPLE_RATE), 440.0) <= HALF_A_CENT


def test_semitones_and_detune_move_the_source():
    """A source a fifth up and 10 cents sharp sounds there."""
    instrument = Instrument(
        sources={'main': Source('sine', semitones=7.0, detune_cents=10.0)},
        envelope=HELD_ENVELOPE,
    )
    samples = render_sound(spec_for(instrument, pitch=Hz(220.0), length=1.0)).samples
    expected = 220.0 * 2.0 ** ((7.0 + 0.1) / 12.0)
    assert cents_between(measured_fundamental(samples, SAMPLE_RATE), expected) <= HALF_A_CENT


def test_a_fixed_pitch_source_ignores_the_note():
    """A source with its own pitch sounds there, whatever the note."""
    instrument = Instrument(
        sources={'main': Source('triangle', pitch=Hz(1000.0))}, envelope=HELD_ENVELOPE
    )
    samples = render_sound(spec_for(instrument, pitch=Hz(220.0), length=1.0)).samples
    assert cents_between(measured_fundamental(samples, SAMPLE_RATE), 1000.0) <= HALF_A_CENT


@pytest.mark.parametrize('wave', ['sine', 'saw'])
def test_a_source_pushed_above_nyquist_is_refused(wave):
    """A source transposed above Nyquist is refused, not aliased."""
    instrument = Instrument(sources={'main': Source(wave, semitones=24.0)}, envelope=HELD_ENVELOPE)
    with pytest.raises(ValueError, match='frequency must be within'):
        render_sound(spec_for(instrument, pitch=Hz(8000.0), length=0.1))


def test_a_note_of_zero_hertz_reads_the_lowest_band():
    """A source at 0 Hz holds its table's first value instead of failing the band lookup."""
    spec = single_note_spec(wave='triangle', hz=440.0, length=0.01, hard_edges=True)
    assert spec.notes is not None
    silent_note = dataclasses.replace(spec.notes[0], hz=0.0)
    samples = render_sound(dataclasses.replace(spec, notes=(silent_note,))).samples
    assert np.max(np.abs(samples)) < 1e-12
