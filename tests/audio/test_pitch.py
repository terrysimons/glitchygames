"""Tests for the pitch types and resolve_pitch."""

import logging

import pytest

from glitchygames.audio import pitch as pitch_module
from glitchygames.audio.pitch import (
    SCALE_INTERVALS,
    Hz,
    Midi,
    Note,
    PitchTable,
    Scale,
    ScaleStep,
    Tuning,
    resolve_pitch,
)


@pytest.fixture(autouse=True)
def fresh_warning_memory():
    """Forget which out-of-range values were already warned about."""
    pitch_module._warned_hertz_values.clear()
    yield
    pitch_module._warned_hertz_values.clear()


def test_note_names_resolve_to_equal_temperament_hertz():
    """Note names resolve to equal temperament hertz."""
    tuning = Tuning()
    assert resolve_pitch('A4', tuning=tuning) == pytest.approx(440.0)
    assert resolve_pitch('C4', tuning=tuning) == pytest.approx(261.6256, abs=1e-4)
    assert resolve_pitch('Bb3', tuning=tuning) == pytest.approx(resolve_pitch('A#3', tuning=tuning))


def test_a_float_is_hertz_and_a_bare_int_is_refused():
    """A float is hertz and a bare int is refused."""
    assert resolve_pitch(880.0, tuning=Tuning()) == 880.0
    with pytest.raises(ValueError, match=r'Midi\(60\)'):
        resolve_pitch(60, tuning=Tuning())


@pytest.mark.parametrize('flag', [True, False])
def test_a_bool_is_refused_like_a_bare_int(flag):
    """A bool is refused like a bare int."""
    with pytest.raises(ValueError, match='ambiguous'):
        resolve_pitch(flag, tuning=Tuning())


def test_midi_and_intervals():
    """Midi and intervals."""
    assert resolve_pitch(Midi(69), tuning=Tuning()) == pytest.approx(440.0)
    octave_up = Note('C4').up(semitones=12)
    assert resolve_pitch(octave_up, tuning=Tuning()) == pytest.approx(2 * 261.6256, abs=1e-3)
    assert Hz(220.0).times(1.5) == pytest.approx(330.0)
    assert Hz(220.0).octave_up() == pytest.approx(440.0)


def test_hz_octaves_and_types():
    """Hz octaves and types."""
    assert Hz(440.0).octave_down() == pytest.approx(220.0)
    assert Hz(110.0).octave_up(2) == pytest.approx(440.0)
    assert isinstance(Hz(110.0).octave_down(2), Hz)


def test_scale_steps_wrap_octaves():
    """Scale steps wrap octaves."""
    assert Scale('C', 'major').step(7) == Note('C5')
    assert Scale('C', 'major_pentatonic').step(2) == Note('E4')


@pytest.mark.parametrize(
    ('kind', 'expected_names'),
    [
        ('major', ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4']),
        ('minor', ['C4', 'D4', 'D#4', 'F4', 'G4', 'G#4', 'A#4']),
        ('major_pentatonic', ['C4', 'D4', 'E4', 'G4', 'A4']),
        ('minor_pentatonic', ['C4', 'D#4', 'F4', 'G4', 'A#4']),
        ('blues', ['C4', 'D#4', 'F4', 'F#4', 'G4', 'A#4']),
        (
            'chromatic',
            ['C4', 'C#4', 'D4', 'D#4', 'E4', 'F4', 'F#4', 'G4', 'G#4', 'A4', 'A#4', 'B4'],
        ),
        ('whole_tone', ['C4', 'D4', 'E4', 'F#4', 'G#4', 'A#4']),
        ('dorian', ['C4', 'D4', 'D#4', 'F4', 'G4', 'A4', 'A#4']),
        ('mixolydian', ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'A#4']),
    ],
)
def test_every_scale_has_its_notes_and_wraps(kind, expected_names):
    """Every scale has its notes and wraps."""
    scale = Scale('C', kind)
    assert [scale.step(number) for number in range(len(expected_names))] == [
        Note(name) for name in expected_names
    ]
    assert scale.step(len(expected_names)) == Note('C5')
    assert scale.step(-1) == Note.from_midi_number(60 - 12 + SCALE_INTERVALS[kind][-1])


def test_every_listed_scale_is_tested():
    """Every listed scale is tested."""
    assert sorted(SCALE_INTERVALS) == sorted(
        [
            'major',
            'minor',
            'major_pentatonic',
            'minor_pentatonic',
            'blues',
            'chromatic',
            'whole_tone',
            'dorian',
            'mixolydian',
        ],
    )


def test_scale_with_a_non_c_root():
    """Scale with a non c root."""
    assert Scale('F#', 'major').step(0) == Note('F#4')
    assert Scale('Bb', 'minor').step(2) == Note('Db5')


@pytest.mark.parametrize(('root', 'kind'), [('H', 'major'), ('C4', 'major'), ('C', 'lydian')])
def test_bad_scales_raise(root, kind):
    """Bad scales raise."""
    with pytest.raises(ValueError, match='scale'):
        Scale(root, kind)


def test_scale_step_resolves_lazily():
    """Scale step resolves lazily."""
    lazy = ScaleStep(Scale('C', 'major'), 2)
    assert lazy.to_note() == Note('E4')
    assert resolve_pitch(lazy, tuning=Tuning()) == pytest.approx(329.6276, abs=1e-4)
    assert lazy == ScaleStep(Scale('C', 'major'), 2)
    assert hash(lazy) == hash(ScaleStep(Scale('C', 'major'), 2))


def test_pitch_table_lookups_equal_the_games_floats():
    """Pitch table lookups equal the games floats."""
    table = PitchTable.from_dict({'C4': 261.63, 'E4': 329.63})
    assert table['E4'] == 329.63
    assert isinstance(table['E4'], Hz)
    assert list(table) == ['C4', 'E4']
    assert len(table) == 2
    assert 'G4' not in table


def test_tuning_moves_every_note_by_one_ratio():
    """Tuning moves every note by one ratio."""
    assert resolve_pitch('A4', tuning=Tuning(a4=432.0)) == pytest.approx(432.0)
    ratio = 432.0 / 440.0
    assert resolve_pitch('C4', tuning=Tuning(a4=432.0)) == pytest.approx(261.6256 * ratio, abs=1e-4)
    assert resolve_pitch(Midi(60), tuning=Tuning(a4=432.0)) == pytest.approx(
        261.6256 * ratio, abs=1e-4
    )


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -1.0, 0.0])
def test_bad_tunings_raise(bad):
    """Bad tunings raise."""
    if bad == 0.0 or bad < 0:
        with pytest.raises(ValueError, match='Tuning'):
            Tuning(a4=bad)
    else:
        with pytest.raises(ValueError, match='Tuning'):
            Tuning(a4=bad)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -1.0, 30000.0])
def test_out_of_range_pitches_raise(bad):
    """Out of range pitches raise."""
    with pytest.raises(ValueError, match='Frequency'):
        resolve_pitch(bad, tuning=Tuning(), sample_rate=44100)


def test_nyquist_follows_the_sample_rate_and_is_inclusive():
    """Nyquist follows the sample rate and is inclusive."""
    assert resolve_pitch(22050.0, tuning=Tuning(), sample_rate=44100) == 22050.0
    with pytest.raises(ValueError, match='Frequency'):
        resolve_pitch(22050.5, tuning=Tuning(), sample_rate=44100)
    with pytest.raises(ValueError, match='Frequency'):
        resolve_pitch(15000.0, tuning=Tuning(), sample_rate=22050)


def test_out_of_range_but_under_nyquist_warns_once_per_value(caplog):
    """Out of range but under nyquist warns once per value."""
    with caplog.at_level(logging.WARNING, logger='game.audio.pitch'):
        resolve_pitch(5.0, tuning=Tuning())
        resolve_pitch(5.0, tuning=Tuning())
        resolve_pitch(20000.0, tuning=Tuning())
        resolve_pitch(440.0, tuning=Tuning())
        resolve_pitch(8.0, tuning=Tuning())
        resolve_pitch(12000.0, tuning=Tuning())
    assert len(caplog.records) == 2
    assert '5.0' in caplog.records[0].getMessage()
    assert '20000.0' in caplog.records[1].getMessage()


def test_note_validation_and_value_semantics():
    """Note validation and value semantics."""
    for bad in ['H4', 'C', '4C', 'C##4', 'c4', 'C10', '']:
        with pytest.raises(ValueError, match='Invalid note name'):
            Note(bad)
    with pytest.raises(ValueError, match='Invalid note name'):
        Note(60)  # type: ignore[arg-type]
    assert Note('C-1').midi_number == 0
    assert Note('Cb4') == Note('B3')
    assert Note('Bb3') == Note('A#3')
    assert hash(Note('Bb3')) == hash(Note('A#3'))
    assert Note('C4') != Note('D4')
    assert Note('C4') != 'C4'
    assert Note('Bb3').name == 'Bb3'
    assert repr(Note('Bb3')) == "Note('Bb3')"
    assert len({Note('Bb3'), Note('A#3')}) == 1


def test_note_moves():
    """Note moves."""
    assert Note('C4').up(semitones=7) == Note('G4')
    assert Note('C4').down(semitones=12) == Note('C3')
    assert Note('C4').up() == Note('C4')
    assert Note('A4').up(cents=100.0) == pytest.approx(440.0 * 2 ** (1 / 12))
    assert isinstance(Note('A4').up(semitones=0.5), Hz)
    assert Note('A4').down(semitones=1, cents=50.0) == pytest.approx(440.0 * 2 ** (-1.5 / 12))
    assert Note('A4').detune(cents=-1200.0) == pytest.approx(220.0)
    assert isinstance(Note('A4').detune(cents=-8), Hz)
    assert Note('A4').to_hz() == pytest.approx(440.0)
    assert Note('A4').to_hz(tuning=Tuning(a4=432.0)) == pytest.approx(432.0)


def test_midi_validation_and_value_semantics():
    """Midi validation and value semantics."""
    assert Midi(0) == 0
    assert Midi(127) == 127
    assert Midi(60) == Midi(60)
    assert hash(Midi(60)) == hash(60)
    for bad in [-1, 128]:
        with pytest.raises(ValueError, match='Midi must be'):
            Midi(bad)
    for bad_type in [60.0, True, '60']:
        with pytest.raises(ValueError, match='Midi needs an int'):
            Midi(bad_type)  # type: ignore[arg-type]
    assert Midi(69).to_hz() == pytest.approx(440.0)
    assert Midi(69).to_hz(tuning=Tuning(a4=432.0)) == pytest.approx(432.0)


def test_unsupported_types_and_bad_names_raise():
    """Unsupported types and bad names raise."""
    with pytest.raises(TypeError, match='list'):
        resolve_pitch([440.0], tuning=Tuning())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match='Invalid note name'):
        resolve_pitch('H9', tuning=Tuning())
