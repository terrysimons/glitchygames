"""Tests for sound specs, instruments, note parsing and identity keys."""

import dataclasses
import os
import re
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs this interpreter
import sys
import textwrap

import pytest

from glitchygames.audio import synth
from glitchygames.audio.instrument import (
    Filter,
    Instrument,
    Noise,
    PitchCurve,
    Source,
    build_spec,
)
from glitchygames.audio.pitch import Hz, Midi, Tuning
from glitchygames.audio.spec import (
    ENVELOPE_PRESETS,
    EnvelopeSpec,
    FilterSpec,
    PlaybackDefaults,
    default_seed,
    identity_key,
    parse_notes,
)
from glitchygames.audio.waves import Wave, current_wave_registry
from glitchygames.engine_context import EngineContext

PULSE = Instrument(wave='pulse_25', envelope='pluck')
NOISE = Instrument(noise='white')


@pytest.fixture(autouse=True)
def own_engine_context():
    """Run each test in a fresh engine context, so registered waves never leak."""
    with EngineContext(name='sound-spec').active():
        yield


def make_spec(  # ruff: ignore[too-many-arguments] - a test helper over build_spec's keywords
    instrument=PULSE,
    *,
    name='x',
    pitch='C5',
    notes=None,
    chord=None,
    length=None,
    transpose=0.0,
    tuning=None,
    sample_rate=44100,
    playback_defaults=None,
):
    """Build a spec with the arguments a test cares about."""
    return build_spec(
        instrument,
        name=name,
        pitch=pitch,
        notes=notes,
        chord=chord,
        length=length,
        transpose=transpose,
        tuning=tuning or Tuning(),
        sample_rate=sample_rate,
        playback_defaults=playback_defaults or PlaybackDefaults(),
    )


def notes_of(spec):
    """A spec's note events, which the test expects to exist."""
    assert spec.notes is not None
    return spec.notes


def test_note_string_becomes_back_to_back_events():
    """A rest advances time but makes no event."""
    events = parse_notes('B5:0.06 _:0.02 E6:0.18', tuning=Tuning())
    assert [round(event.start_seconds, 6) for event in events] == [0.0, 0.08]
    assert events[1].length_seconds == pytest.approx(0.18)


def test_note_sequence_accepts_any_pitch_type_and_rests():
    """Pairs take Hz, Midi, names and '_' rests."""
    events = parse_notes([(Hz(440.0), 0.1), ('_', 0.1), (Midi(69), 0.1)], tuning=Tuning())
    assert [event.hz for event in events] == pytest.approx([440.0, 440.0])
    assert [round(event.start_seconds, 6) for event in events] == [0.0, 0.2]


@pytest.mark.parametrize('bad', ['', 'C4', 'C4:abc', 'C4:0', 'C4:-1'])
def test_bad_note_strings_are_refused(bad):
    """Empty, tokens without seconds, non-numbers and non-positive lengths are errors."""
    with pytest.raises(ValueError, match=r'note|empty|length'):
        parse_notes(bad, tuning=Tuning())


def test_pitch_with_notes_or_chord_is_refused():
    """The spec's mutual exclusion points at transpose."""
    with pytest.raises(ValueError, match='transpose'):
        make_spec(pitch='C4', notes='C4:0.1')
    with pytest.raises(ValueError, match='transpose'):
        make_spec(pitch='C4', chord=('C4', 'E4'))


def test_chord_is_simultaneous_events_of_one_length():
    """Every chord pitch starts at zero and lasts the given length."""
    spec = make_spec(pitch=None, chord=('C4', 'E4', 'G4'), length=0.5)
    assert {event.start_seconds for event in notes_of(spec)} == {0.0}
    assert len(notes_of(spec)) == 3
    assert {event.length_seconds for event in notes_of(spec)} == {0.5}


def test_default_length_is_a_quarter_second():
    """A single pitch and a chord default to 0.25 s."""
    assert notes_of(make_spec())[0].length_seconds == 0.25
    assert notes_of(make_spec(pitch=None, chord=('C4',)))[0].length_seconds == 0.25


def test_transpose_shifts_notes_and_chords_by_semitones():
    """Twelve semitones doubles every frequency."""
    plain = make_spec(pitch=None, notes='A4:0.1')
    shifted = make_spec(pitch=None, notes='A4:0.1', transpose=12.0)
    assert notes_of(shifted)[0].hz == pytest.approx(notes_of(plain)[0].hz * 2.0)
    chord = make_spec(pitch=None, chord=('A4',), transpose=-12.0)
    assert notes_of(chord)[0].hz == pytest.approx(220.0)


def test_argument_conflicts_are_refused():
    """Transpose on a single pitch, length on notes, bad lengths and empty chords."""
    with pytest.raises(ValueError, match='transpose applies'):
        make_spec(transpose=2.0)
    with pytest.raises(ValueError, match='length does not apply'):
        make_spec(pitch=None, notes='C4:0.1', length=0.2)
    with pytest.raises(ValueError, match='above zero'):
        make_spec(length=0.0)
    with pytest.raises(ValueError, match='chord cannot be empty'):
        make_spec(pitch=None, chord=())


def test_no_pitch_leaves_notes_to_the_renderer():
    """Without pitch, notes or chord there are no events."""
    assert make_spec(pitch=None).notes is None


def test_a_pitched_instrument_with_a_length_but_no_pitch_is_refused():
    """The length would have nothing to attach to."""
    with pytest.raises(ValueError, match='needs a pitch'):
        make_spec(pitch=None, length=0.5)


def test_unpitched_instrument_scales_rates_by_pitch_over_440():
    """A noise-only instrument given a pitch sets unpitched_scale; pitched ones keep 1.0."""
    assert make_spec(NOISE, pitch=Hz(880.0)).unpitched_scale == pytest.approx(2.0)
    assert make_spec(NOISE, pitch=None).unpitched_scale == 1.0
    assert make_spec(PULSE, pitch=Hz(880.0)).unpitched_scale == 1.0
    assert make_spec(NOISE, pitch=None, chord=(Hz(880.0),)).unpitched_scale == 1.0


def test_unpitched_instrument_with_only_a_length_gets_a_reference_event():
    """The length is kept in the spec, so it is part of the identity."""
    spec = make_spec(NOISE, pitch=None, length=0.7)
    assert (notes_of(spec)[0].hz, notes_of(spec)[0].length_seconds) == (440.0, 0.7)


def test_identity_changes_with_any_identifying_field_and_not_otherwise():
    """Equal specs share a key; pitch and sample rate change it."""
    first, same, other_pitch, other_rate = (
        make_spec(pitch='C5'),
        make_spec(pitch='C5'),
        make_spec(pitch='D5'),
        make_spec(pitch='C5', sample_rate=48000),
    )
    assert identity_key(first) == identity_key(same)
    assert len({identity_key(first), identity_key(other_pitch), identity_key(other_rate)}) == 3


def test_identity_key_is_128_bit_hex():
    """32 hex digits."""
    key = identity_key(make_spec())
    assert len(key) == 32
    int(key, 16)


@pytest.mark.parametrize(
    'changes',
    [
        {'name': 'other'},
        {'tuning': Tuning(a4=432.0)},
        {'instrument': Instrument(wave='pulse_25', envelope='pad')},
        {'instrument': Instrument(wave='pulse_25', drive=1.0)},
        {'instrument': Instrument(wave='pulse_25', seed=7)},
        {'instrument': Instrument(wave='pulse_25', filter=Filter('low_pass', 800.0))},
        {'instrument': Instrument(wave='sine')},
        {'instrument': Instrument(wave=Wave('pulse', duty=0.3))},
        {'instrument': Instrument(sources={'a': Wave('square').detuned(cents=5.0)})},
    ],
)
def test_identity_changes_with_name_tuning_and_instrument(changes):
    """Each of these is part of what the sound is."""
    assert identity_key(make_spec(**changes)) != identity_key(make_spec())


def test_identity_ignores_playback_defaults():
    """Playback is not what the sound is."""
    loud = make_spec(playback_defaults=PlaybackDefaults(bus='music', volume=0.2, loop=True))
    assert identity_key(loud) == identity_key(make_spec())


def test_identity_key_is_stable_across_processes():
    """Hash randomization must not change the key: run it under two hash seeds."""
    program = textwrap.dedent(
        """
        from glitchygames.audio.instrument import Instrument, build_spec
        from glitchygames.audio.pitch import Tuning
        from glitchygames.audio.spec import PlaybackDefaults, identity_key
        from glitchygames.audio.waves import Wave
        instrument = Instrument(sources={'a': Wave('saw'), 'b': Wave('saw').detuned(cents=7)})
        spec = build_spec(instrument, name='x', pitch='C5', notes=None, chord=None, length=None,
                          transpose=0.0, tuning=Tuning(), sample_rate=44100,
                          playback_defaults=PlaybackDefaults())
        print(identity_key(spec))
        """
    )
    keys = {
        subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed interpreter and program
            [sys.executable, '-c', program],
            check=True,
            capture_output=True,
            text=True,
            # The parent's environment with the seed and drivers set: Windows' Python needs
            # SYSTEMROOT and PATH (numpy's DLLs) to start
            env={
                **os.environ,
                'PYTHONHASHSEED': seed,
                'SDL_AUDIODRIVER': 'dummy',
                'SDL_VIDEODRIVER': 'dummy',
            },
        ).stdout.splitlines()[-1]
        for seed in ('1', '2')
    }
    assert len(keys) == 1
    assert keys == {
        identity_key(
            make_spec(Instrument(sources={'a': Wave('saw'), 'b': Wave('saw').detuned(cents=7)}))
        )
    }


def test_default_seed_is_derived_from_the_name_not_the_run():
    """Same name, same seed; another name, another seed; an instrument seed wins."""
    assert make_spec(name='coin').seed == make_spec(name='coin').seed != make_spec(name='thud').seed
    assert make_spec(name='coin').seed == default_seed('coin')
    assert make_spec(Instrument(wave='sine', seed=99), name='coin').seed == 99


def test_instrument_takes_exactly_one_of_wave_noise_sources():
    """Zero or several of the three, or too many sources, are refused."""
    with pytest.raises(ValueError, match='exactly one'):
        Instrument(wave='square', noise='white')
    with pytest.raises(ValueError, match='exactly one'):
        Instrument()
    with pytest.raises(ValueError, match='at most 4'):
        Instrument(sources={str(index): Wave('sine') for index in range(5)})
    with pytest.raises(ValueError, match='cannot be empty'):
        Instrument(sources={})


def test_instrument_validates_drive_profile_and_envelope():
    """Out-of-range drive and unknown names are refused at construction."""
    with pytest.raises(ValueError, match='drive'):
        Instrument(wave='sine', drive=21.0)
    with pytest.raises(ValueError, match='profile'):
        Instrument(wave='sine', profile='granular')
    with pytest.raises(ValueError, match='envelope'):
        Instrument(wave='sine', envelope='gong')


def test_instrument_is_hashable_by_content():
    """Equal instruments are equal and hash equal; different ones differ."""
    first, same, other = Instrument(wave='sine'), Instrument(wave='sine'), Instrument(wave='saw')
    assert first == same
    assert hash(first) == hash(same)
    assert first != other
    assert first != 'sine'
    assert len({first, same, other}) == 2
    assert 'main' in repr(first)


def test_instrument_exposes_its_settings():
    """Properties echo the constructor."""
    instrument = Instrument(
        noise=Noise('lfsr', bits=7), live=True, normalize=True, hard_edges=True, seed=3
    )
    assert instrument.is_unpitched
    assert (instrument.live, instrument.normalize, instrument.hard_edges, instrument.seed) == (
        True,
        True,
        True,
        3,
    )
    assert instrument.drive == 0.0
    assert instrument.filter is None
    assert not Instrument(wave='sine').is_unpitched


def test_wave_names_resolve_when_the_spec_is_built():
    """A wave registered after the instrument is built still works."""
    instrument = Instrument(wave='ghost')
    ghost = Wave.mix(sine=0.5, triangle=0.5)
    current_wave_registry().register('ghost', ghost)
    assert make_spec(instrument).sources[0].wave == ghost


def test_unknown_wave_name_fails_at_build_not_construction():
    """The instrument can be made; the build names the missing wave."""
    instrument = Instrument(wave='nope')
    with pytest.raises(ValueError, match="unknown wave 'nope'"):
        make_spec(instrument)


def test_envelope_presets_and_legacy_envelopes():
    """Presets exist, and a synth.Envelope converts to a linear spec."""
    assert set(ENVELOPE_PRESETS) == {'pluck', 'pad', 'organ', 'percussive', 'swell'}
    legacy = synth.Envelope(attack=0.01, decay=0.02, sustain_level=0.5, release=0.1)
    assert Instrument(wave='sine', envelope=legacy).envelope == EnvelopeSpec(
        0.01, 0.02, 0.5, 0.1, 'linear'
    )
    custom = EnvelopeSpec(0.1, 0.1, 0.5, 0.1, 'steps(4)')
    assert Instrument(wave='sine', envelope=custom).envelope is custom


@pytest.mark.parametrize('cutoff', [22050.0, 30000.0])
def test_a_filter_cutoff_at_or_above_nyquist_is_refused_when_the_spec_is_built(cutoff):
    """build_spec knows the sample rate, so it refuses a cutoff the FIR could not make."""
    expected = f'filter cutoff {cutoff} Hz must be below Nyquist (22050.0 Hz at 44100 Hz)'
    with pytest.raises(ValueError, match=re.escape(expected)):
        make_spec(Instrument(wave='sine', filter=Filter('low_pass', cutoff)))
    layered = Instrument(
        sources={'main': Source('sine', filter=Filter('high_pass', cutoff))}, envelope='organ'
    )
    with pytest.raises(ValueError, match='Nyquist'):
        make_spec(layered)


def test_a_cutoff_just_under_nyquist_is_accepted():
    """A cutoff below Nyquist builds."""
    spec = make_spec(Instrument(wave='sine', filter=Filter('low_pass', 22049.0)))
    assert spec.filter is not None


def test_envelope_and_filter_validation():
    """Bad envelope and filter values are refused."""
    with pytest.raises(ValueError, match='negative'):
        EnvelopeSpec(-1.0, 0.0, 0.5, 0.0)
    with pytest.raises(ValueError, match='sustain'):
        EnvelopeSpec(0.0, 0.0, 1.5, 0.0)
    with pytest.raises(ValueError, match='curve'):
        EnvelopeSpec(0.0, 0.0, 0.5, 0.0, 'wobbly')
    with pytest.raises(ValueError, match='kind'):
        FilterSpec('band_pass', 100.0)
    with pytest.raises(ValueError, match='cutoff'):
        FilterSpec('low_pass', 0.0)


def test_noise_validation_and_layering():
    """Noise checks its kind, width and level; its level multiplies the source's."""
    with pytest.raises(ValueError, match='kind'):
        Noise('pink')
    with pytest.raises(ValueError, match='bits'):
        Noise('lfsr', bits=8)
    with pytest.raises(ValueError, match='level'):
        Noise(level=2.0)
    with pytest.raises(ValueError, match='level'):
        Source('sine', level=-0.1)
    spec = make_spec(
        Instrument(sources={'grit': Source(Noise('white', level=0.5), level=0.5)}), pitch=None
    )
    assert spec.sources[0].level == pytest.approx(0.25)
    assert spec.sources[0].wave is None


def test_noise_rate_is_resolved_to_hertz():
    """An LFSR rate given as a pitch becomes rate_hz; None stays None."""
    spec = make_spec(Instrument(noise=Noise('lfsr', rate=Hz(4000.0), seed=5)), pitch=None)
    assert (spec.sources[0].noise.rate_hz, spec.sources[0].noise.seed) == (4000.0, 5)
    assert make_spec(NOISE, pitch=None).sources[0].noise.rate_hz is None


def test_detuned_wave_is_a_source_and_layers_resolve():
    """Wave.detuned gives a Source; build_spec carries the detune, pitch override and glide."""
    detuned = Wave('saw').detuned(cents=7)
    assert isinstance(detuned, Source)
    layered = Source(
        'pulse',
        semitones=12.0,
        pitch='A4',
        pitch_curve=PitchCurve(to=Hz(220.0), seconds=0.1, easing='ease_out'),
        envelope='percussive',
        filter=Filter('high_pass', 500.0),
    )
    spec = make_spec(Instrument(sources={'a': Wave('saw'), 'b': detuned, 'c': layered}))
    assert [source.detune_cents for source in spec.sources] == [0.0, 7, 0.0]
    last = spec.sources[2]
    assert (last.semitones, last.fixed_hz, last.duty) == (12.0, 440.0, 0.5)
    assert (last.pitch_curve.target_hz, last.pitch_curve.seconds) == (220.0, 0.1)
    assert last.envelope == ENVELOPE_PRESETS['percussive']
    assert last.filter == FilterSpec('high_pass', 500.0)
    assert make_spec(Instrument(wave=Wave('pulse', duty=0.3))).sources[0].duty == 0.3


def test_spec_carries_instrument_settings_and_tuning():
    """Drive, filter, flags, tuning and defaults are copied through."""
    defaults = PlaybackDefaults(bus='music', volume=0.5, pan=-0.5, priority=10, loop=True)
    spec = make_spec(
        Instrument(wave='sine', drive=3.0, filter=Filter('low_pass', 900.0), live=True),
        tuning=Tuning(a4=432.0),
        playback_defaults=defaults,
    )
    assert (spec.drive, spec.live, spec.tuning_a4) == (3.0, True, 432.0)
    assert spec.filter == FilterSpec('low_pass', 900.0)
    assert spec.playback_defaults == defaults
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.drive = 1.0  # type: ignore[misc]


def test_wave_identity_digest_distinguishes_waves():
    """Equal waves share a digest; a different duty or shape does not."""
    assert Wave('saw').identity_digest() == Wave('saw').identity_digest()
    assert Wave('pulse', duty=0.3).identity_digest() != Wave('pulse', duty=0.4).identity_digest()
    assert Wave('sine').identity_digest() != Wave('triangle').identity_digest()


@pytest.mark.parametrize(
    ('integer_form', 'float_form'),
    [
        (
            {'instrument': Instrument(sources={'a': Source('sine', level=1, semitones=0)})},
            {'instrument': Instrument(sources={'a': Source('sine', level=1.0, semitones=0.0)})},
        ),
        (
            {'instrument': Instrument(sources={'a': Source('sine', detune_cents=0)})},
            {'instrument': Instrument(sources={'a': Source('sine', detune_cents=0.0)})},
        ),
        (
            {'instrument': Instrument(wave='sine', drive=0, filter=Filter('low_pass', 800))},
            {'instrument': Instrument(wave='sine', drive=0.0, filter=Filter('low_pass', 800.0))},
        ),
        (
            {'instrument': Instrument(wave='sine', envelope=EnvelopeSpec(0, 0, 1, 1))},
            {'instrument': Instrument(wave='sine', envelope=EnvelopeSpec(0.0, 0.0, 1.0, 1.0))},
        ),
        (
            {
                'instrument': Instrument(
                    sources={'a': Source('sine', pitch_curve=PitchCurve(Hz(220.0), 1))}
                )
            },
            {
                'instrument': Instrument(
                    sources={'a': Source('sine', pitch_curve=PitchCurve(Hz(220.0), 1.0))}
                )
            },
        ),
        ({'length': 1}, {'length': 1.0}),
        ({'pitch': None, 'notes': [('C4', 1)]}, {'pitch': None, 'notes': [('C4', 1.0)]}),
        (
            {'pitch': None, 'chord': ('C4',), 'transpose': 12},
            {'pitch': None, 'chord': ('C4',), 'transpose': 12.0},
        ),
        ({'tuning': Tuning(a4=440)}, {'tuning': Tuning(a4=440.0)}),
    ],
)
def test_an_int_and_a_float_give_equal_specs_and_one_identity_key(integer_form, float_form):
    """Whether a number was written 1 or 1.0, it is the same sound with the same key."""
    from_int, from_float = make_spec(**integer_form), make_spec(**float_form)
    assert from_int == from_float
    assert identity_key(from_int) == identity_key(from_float)


def test_spec_float_fields_are_always_floats():
    """No int survives in a float field, so the canonical JSON cannot differ."""
    spec = make_spec(Instrument(sources={'a': Source('sine', level=1, semitones=0)}), length=1)
    assert type(spec.sources[0].level) is float
    assert type(spec.sources[0].semitones) is float
    assert type(notes_of(spec)[0].length_seconds) is float
