"""The instrument catalog: every entry builds, renders across its range and plays its pitch."""

from functools import partial
from typing import NamedTuple

import numpy as np
import pytest

from glitchygames.audio import instruments
from glitchygames.audio.instrument import Filter, Instrument
from glitchygames.audio.instruments import CatalogEntry, Family, Tag
from glitchygames.audio.instruments.registry import (
    FAMILY_TABLES,
    aliases_from,
    catalog_from,
    sound_alikes_from,
)
from glitchygames.audio.instruments.timbres import (
    Course,
    Formant,
    Partial,
    Tone,
    blown,
    decibels_to_level,
    drum,
    falling_series,
    formant_series,
    harmonics_from_levels,
    noise_layer,
    plucked,
    plucked_series,
    rubbed,
    struck,
    with_drones,
)
from glitchygames.audio.instruments.voices import FORMANT_TABLE
from glitchygames.audio.pitch import Note
from glitchygames.audio.render import render_sound
from glitchygames.audio.waves import Wave
from tests.audio.render_specs import SAMPLE_RATE, spec_for

NOTE_SECONDS = 0.4
# Families whose tones are harmonic: their sound repeats at the note's period
HARMONIC_FAMILIES = {
    Family.FLUTES,
    Family.CLARINETS,
    Family.SAXOPHONES,
    Family.DOUBLE_REEDS,
    Family.FREE_REEDS,
    Family.BRASS,
    Family.BOWED_STRINGS,
    Family.PLUCKED_STRINGS,
    Family.HARPS,
    Family.KEYBOARDS,
    Family.ORGANS,
    Family.ELECTROMECHANICAL,
    Family.ELECTRONIC,
    Family.VOICES,
    Family.CHOIRS,
}
# Entries in those families whose sound does not repeat at the note's period, and why
NOT_PERIODIC_AT_THE_NOTE = {
    'tine electric piano': 'its bell partial is 7.1x, not a harmonic',
    'toy piano': 'struck rods: partials at 2.76x and 5.40x',
    'celesta': 'a struck bar (its 4x partial is harmonic, but the attack noise is long)',
    'synth bass': 'a square an octave below: the sound repeats every two periods',
}

# Drawbar organs with the 16' bar (harmonic 0.5) drawn: the 8' bar is the note, but the sound
# repeats every two of its periods, as a real organ's does
SIXTEEN_FOOT_ORGANS = {
    entry.name
    for entry in (
        instruments.entries(family=Family.ORGANS)
        + instruments.entries(family=Family.ELECTROMECHANICAL)
    )
    for _, source in instruments.get(entry.name).sources
    if not isinstance(source.content, str)
    and getattr(source.content, 'note_periods_per_cycle', 1) == 2
}


def rendered(instrument: Instrument, *, pitch: str, name: str = 'catalog-test') -> np.ndarray:
    """One note of the instrument.

    Returns:
        The samples.
    """
    return render_sound(spec_for(instrument, name=name, pitch=pitch, length=NOTE_SECONDS)).samples


def repetition_at(samples: np.ndarray, *, period_seconds: float) -> float:
    """How well the samples repeat after ``period_seconds`` (normalized correlation, 1 = exactly).

    Returns:
        The correlation.
    """
    lag = round(period_seconds * SAMPLE_RATE)
    earlier, later = samples[:-lag], samples[lag:]
    return float(np.dot(earlier, later) / (np.linalg.norm(earlier) * np.linalg.norm(later)))


def best_period_near(samples: np.ndarray, *, hertz: float) -> float:
    """The period within a semitone of 1 / ``hertz`` at which the samples repeat best.

    Returns:
        The period's frequency in hertz.
    """
    semitone = 2.0 ** (1.0 / 12.0)
    shortest = int(SAMPLE_RATE / (hertz * semitone))
    longest = int(SAMPLE_RATE / (hertz / semitone)) + 1
    scores = [
        (repetition_at(samples, period_seconds=lag / SAMPLE_RATE), lag)
        for lag in range(max(2, shortest), longest + 1)
    ]
    _, lag = max(scores)
    return SAMPLE_RATE / lag


def test_the_catalog_holds_every_family_with_unique_valid_names():
    """Every family has entries, and no name is used twice."""
    names = instruments.names()
    assert len(names) == len(set(names))
    assert len(names) >= 400
    assert set(instruments.families()) == {entry.family for entry in instruments.entries()}
    assert instruments.families() == tuple(Family)


@pytest.mark.parametrize(
    'voice',
    [
        'soprano',
        'mezzo soprano',
        'alto',
        'treble',
        'countertenor',
        'tenor',
        'baritone',
        'bass',
        'basso profundo',
    ],
)
def test_every_voice_range_sings_every_vowel_and_hums(voice):
    """Each voice range sings ah, eh, ee, oh and oo, and hums."""
    for sound in ('ah', 'eh', 'ee', 'oh', 'oo', 'hum'):
        assert instruments.entry(f'{voice} {sound}').family == Family.VOICES


@pytest.mark.parametrize(
    'family_names',
    [
        (
            'sopranino saxophone',
            'soprano saxophone',
            'alto saxophone',
            'tenor saxophone',
            'baritone saxophone',
            'bass saxophone',
            'contrabass saxophone',
        ),
        (
            'sopranino recorder',
            'soprano recorder',
            'alto recorder',
            'tenor recorder',
            'bass recorder',
            'great bass recorder',
            'contrabass recorder',
        ),
        ('alto trombone', 'trombone', 'bass trombone', 'contrabass trombone'),
        ('piccolo', 'flute', 'alto flute', 'bass flute', 'contra alto flute', 'contrabass flute'),
        ('choir soprano ah', 'choir alto ah', 'choir tenor ah', 'choir bass ah'),
    ],
)
def test_sized_families_descend_from_highest_to_lowest(family_names):
    """A family's sizes (sopranino to contrabass) go down in range."""
    lowest_notes = [Note(instruments.entry(name).lowest or '').midi_number for name in family_names]
    assert lowest_notes == sorted(lowest_notes, reverse=True)


@pytest.mark.parametrize('name', instruments.names())
def test_every_instrument_renders_across_its_range(name):
    """Each entry renders its lowest, middle and highest notes: finite, audible, unclipped."""
    entry = instruments.entry(name)
    instrument = instruments.get(name)
    playing_range = entry.playing_range
    pitches = (
        [playing_range[0].name, entry.middle_note().name, playing_range[1].name]
        if playing_range is not None
        else ['A4']
    )
    for pitch in pitches:
        samples = rendered(instrument, pitch=pitch, name=name)
        assert np.all(np.isfinite(samples)), (name, pitch)
        assert 0.05 < np.max(np.abs(samples)) <= 1.0, (name, pitch)


@pytest.mark.parametrize(
    'name',
    [
        entry.name
        for entry in instruments.entries()
        if entry.family in HARMONIC_FAMILIES
        and entry.name not in NOT_PERIODIC_AT_THE_NOTE
        # An unpitched entry has no note to repeat at (batch 6's drum-machine voices)
        and entry.pitched
    ],
)
def test_harmonic_instruments_sound_their_note(name):
    """A harmonic instrument repeats at its note's period, not an octave up."""
    entry = instruments.entry(name)
    note = entry.middle_note()
    hertz = float(note.to_hz()) / (2.0 if name in SIXTEEN_FOOT_ORGANS else 1.0)
    samples = rendered(instruments.get(name), pitch=note.name, name=name)
    held = samples[round(0.15 * SAMPLE_RATE) : round(0.35 * SAMPLE_RATE)]
    found = best_period_near(held, hertz=hertz)
    assert abs(1200.0 * np.log2(found / hertz)) < 30.0, (name, note.name, found)
    whole = repetition_at(held, period_seconds=1.0 / hertz)
    assert whole > 0.75, (name, whole)
    # Not an octave up: the sound repeats better at the note's period than at half of it
    assert whole > repetition_at(held, period_seconds=0.5 / hertz) + 0.05, name


def test_the_sixteen_foot_organs_are_the_drawbar_settings_that_draw_it():
    """The organs checked at two periods are exactly those drawing the 16' bar."""
    assert {
        'pipe organ plenum',
        'tonewheel organ jazz',
        'tonewheel organ full',
        'tonewheel organ ballad',
        'tonewheel organ rock',
        'tonewheel organ gospel',
        'tonewheel organ percussion second',
        'tonewheel organ percussion third',
    } == SIXTEEN_FOOT_ORGANS


def test_unpitched_entries_ignore_the_pitch():
    """A drum has no range, and sounds the same at any pitch."""
    kick = instruments.get('kick drum')
    assert not instruments.entry('kick drum').pitched
    assert instruments.entry('kick drum').playing_range is None
    assert instruments.entry('kick drum').middle_note() == Note('A4')
    assert np.array_equal(rendered(kick, pitch='A4'), rendered(kick, pitch='C2'))


def test_get_builds_once_and_names_are_looked_up_with_suggestions():
    """The catalog keeps what get builds; an unknown name suggests close ones."""
    assert instruments.get('violin') is instruments.get('violin')
    with pytest.raises(KeyError, match='did you mean violin'):
        instruments.entry('violn')
    with pytest.raises(KeyError, match=r"no instrument named 'kazoo_of_doom' in the catalog\"$"):
        instruments.entry('kazoo_of_doom')


def test_the_catalog_refuses_a_name_used_twice():
    """Two entries with one name are refused when the catalog is assembled."""
    assert catalog_from(FAMILY_TABLES) == instruments.CATALOG
    flute = instruments.entry('flute')
    with pytest.raises(ValueError, match="names 'flute' twice"):
        catalog_from(((flute,), (flute,)))


def test_a_family_lists_only_its_own():
    """A family's listing holds only that family, in catalog order."""
    brass = instruments.entries(family=Family.BRASS)
    assert brass
    assert {entry.family for entry in brass} == {Family.BRASS}
    assert instruments.names(family=Family.BAGPIPES)[0] == 'highland bagpipe'


def test_entry_rules():
    """An entry refuses a bad name, a one-ended range, an upside-down range, a bad note."""
    for bad_name in ('Bad Name', 'bad_name', 'bad  name', ' bad', 'bad '):
        with pytest.raises(ValueError, match='lower-case words'):
            CatalogEntry(
                bad_name, 'Bad', Family.FLUTES, 'C4', 'C5', lambda: instruments.get('flute')
            )
    with pytest.raises(ValueError, match='both ends'):
        CatalogEntry('half', 'Half', Family.FLUTES, 'C4', None, lambda: instruments.get('flute'))
    with pytest.raises(ValueError, match='above highest'):
        CatalogEntry(
            'upside down', 'Upside', Family.FLUTES, 'C5', 'C4', lambda: instruments.get('flute')
        )
    with pytest.raises(ValueError, match='Invalid note name'):
        CatalogEntry(
            'nonsense', 'Nonsense', Family.FLUTES, 'H4', 'C5', lambda: instruments.get('flute')
        )


def test_overtone_series():
    """The series shapes: slopes, odd harmonics, pluck nodes, formant peaks and skirts."""
    assert decibels_to_level(-20.0) == pytest.approx(0.1)
    assert falling_series(count=3, decibels_per_octave=6.0206) == pytest.approx(
        (1.0, 0.5, 1 / 3), rel=1e-3
    )
    assert falling_series(count=4, decibels_per_octave=0.0, odd_only=True) == (1.0, 0.0, 1.0, 0.0)
    # Plucked at a quarter of the length: the fourth harmonic is not excited
    assert plucked_series(count=4, decibels_per_octave=0.0, pluck_position=0.25)[3] == (
        pytest.approx(0.0, abs=1e-12)
    )
    peaks = formant_series(
        fundamental_hz=100.0,
        source_decibels_per_octave=0.0,
        formants=(Formant(hertz=500.0, bandwidth=50.0, decibels=0.0),),
    )
    assert max(peaks) == peaks[4] == 1.0
    # A resonance's skirt keeps a far-off fundamental audible (a soprano's "ee": F1 at 270 Hz)
    soprano_ee = formant_series(
        fundamental_hz=523.0,
        formants=(
            Formant(hertz=270.0, bandwidth=60.0, decibels=0.0),
            Formant(hertz=2140.0, bandwidth=90.0, decibels=-12.0),
        ),
    )
    assert soprano_ee[0] == max(soprano_ee)
    assert harmonics_from_levels((1.0, 0.00001, 0.5)).octave == 0.0


def test_rubbed_partials_swell_and_hold():
    """A rubbed sound swells in over its attack and then sustains while the note is held."""
    instrument = rubbed(
        [
            Partial(ratio=1.0, level=1.0, ring_seconds=0.0),
            Partial(ratio=2.76, level=0.3, ring_seconds=0.0),
        ],
        attack=0.2,
        release=0.3,
    )
    samples = rendered(instrument, pitch='A4')
    peak = np.max(np.abs(samples))
    first_twenty_milliseconds = np.max(np.abs(samples[: round(0.02 * SAMPLE_RATE)]))
    held_window = samples[round(0.33 * SAMPLE_RATE) : round(0.35 * SAMPLE_RATE)]
    assert first_twenty_milliseconds < 0.3 * peak
    assert np.max(np.abs(held_window)) >= 0.5 * peak
    with pytest.raises(ValueError, match='1 to 4 partials'):
        rubbed([Partial(ratio=1.0, level=1.0, ring_seconds=0.0)] * 5, attack=0.2, release=0.3)
    with pytest.raises(ValueError, match='1 to 4 partials'):
        rubbed((), attack=0.2, release=0.3)


def test_timbre_shapes_refuse_more_layers_than_four_sources():
    """Each shape refuses more layers than an instrument has sources."""
    with pytest.raises(ValueError, match='between 1 and 32'):
        harmonics_from_levels(())
    with pytest.raises(ValueError, match='at most two extra courses'):
        plucked((1.0,), ring_seconds=1.0, courses=(Course(), Course(), Course()))
    with pytest.raises(ValueError, match='1 to 3 partials'):
        struck([Partial(ratio=1.0, level=1.0, ring_seconds=1.0)] * 4, release=1.0, mallet=0.1)
    with pytest.raises(ValueError, match='1 to 4 partials'):
        struck((), release=1.0)
    with pytest.raises(ValueError, match='noise or 1 to 4 tones'):
        drum()
    with pytest.raises(ValueError, match='noise or 1 to 3 tones'):
        drum(tones=[Tone(hertz=100.0, ring_seconds=0.1)] * 4, noise=0.5)
    chanter = blown((1.0,), attack=0.01, release=0.01, breath=0.01)
    with pytest.raises(ValueError, match='room for 2 drones'):
        with_drones(
            chanter,
            drones=((100.0, 0.5),) * 3,
            drone_wave=Wave('sine'),
        )


def test_timbre_shapes_build_their_filters():
    """The shapes pass their filters on, a bagpipe its chanter filter."""
    assert noise_layer(level=0.5, high_pass=1000.0).filter == Filter(
        kind='high_pass', cutoff=1000.0
    )
    assert noise_layer(level=0.5).filter is None
    muted = blown((1.0,), attack=0.01, release=0.01, high_pass=500.0)
    assert muted.filter is not None
    assert muted.filter.kind == 'high_pass'
    piped = with_drones(
        blown((1.0,), attack=0.01, release=0.01, low_pass=3000.0),
        drones=((100.0, 0.5),),
        drone_wave=Wave('sine'),
    )
    assert piped.filter is not None
    assert piped.filter.cutoff_hz == 3000.0
    assert [name for name, _ in piped.sources] == ['tone', 'drone_1']


def test_the_o_vowels_keep_csounds_bandwidths():
    """The soprano and tenor "o" rows match the Csound manual's Tables D.19 and D.24.

    An audit found the two rows' bandwidths swapped
    (https://csound.com/docs/manual/MiscFormants.html).
    """
    soprano = [bandwidth for _, _, bandwidth in FORMANT_TABLE['soprano']['o']]
    tenor = [bandwidth for _, _, bandwidth in FORMANT_TABLE['tenor']['o']]
    assert soprano == [40, 80, 100, 120, 120]
    assert tenor == [70, 80, 100, 130, 135]


def test_organ_ranges_start_at_their_keys_eight_foot_pitch():
    """An organ's range is its manual at 8' pitch: from C2, not the 16' octave below."""
    tonewheel_organs = tuple(instruments.entry(name) for name in MOVED_TONEWHEEL_ORGANS)
    for organ in (*instruments.entries(family=Family.ORGANS), *tonewheel_organs):
        playing_range = organ.playing_range
        assert playing_range is not None
        assert playing_range[0].midi_number >= Note('C2').midi_number, organ.name


def test_lookups_lowercase_their_input():
    """entry, get, names and entries find a name or family in any case."""
    assert instruments.entry('Tenor Saxophone') is instruments.entry('tenor saxophone')
    assert instruments.entry('TENOR SAXOPHONE').name == 'tenor saxophone'
    assert instruments.get('Violin') is instruments.get('violin')
    assert instruments.names(family='Double Reeds') == instruments.names(family=Family.DOUBLE_REEDS)
    assert instruments.entries(family='BRASS') == instruments.entries(family=Family.BRASS)


def test_lookups_refuse_unknown_names_in_any_case():
    """An unknown name or family still fails, and the suggestions use the lowercased name."""
    with pytest.raises(KeyError, match='did you mean tenor saxophone'):
        instruments.entry('Tenor Saxofone')
    with pytest.raises(KeyError, match="'Kazoo Deluxe'"):
        instruments.get('Kazoo Deluxe')
    with pytest.raises(ValueError, match='spoons'):
        instruments.names(family='Spoons')


def test_a_tag_lists_exactly_its_tagged_entries():
    """names(tag=...) is every entry carrying that tag, in catalog order, alone or with family."""
    tagged = instruments.names(tag=Tag.MECHANICAL)
    assert tagged == tuple(
        entry.name for entry in instruments.entries() if Tag.MECHANICAL in entry.tags
    )
    assert instruments.names(tag='Mechanical') == tagged
    assert instruments.names(family=Family.BRASS, tag=Tag.MECHANICAL) == ()
    assert instruments.entries(tag=Tag.MECHANICAL) == tuple(
        instruments.entry(name) for name in tagged
    )
    with pytest.raises(ValueError, match='self playing'):
        instruments.names(tag='self playing')


def test_every_entry_tag_is_a_tag_member():
    """Tags are members of the closed Tag enum, never bare strings."""
    for entry in instruments.entries():
        assert all(type(tag) is Tag for tag in entry.tags), entry.name


def test_an_entry_refuses_a_string_tag():
    """A string equal to a tag's value is still refused: tags cannot drift into synonyms."""
    flute = instruments.entry('flute')
    with pytest.raises(TypeError, match="tag 'mechanical' must be a Tag"):
        CatalogEntry(
            'test flute',
            'Test flute',
            Family.FLUTES,
            'C4',
            'C7',
            flute.build,
            tags=frozenset({'mechanical'}),  # pyright: ignore[reportArgumentType] - the refusal
        )
    assert (
        CatalogEntry('test flute', 'Test flute', Family.FLUTES, 'C4', 'C7', flute.build).tags
        == frozenset()
    )


def test_an_entry_keeps_its_tag_members():
    """A Tag member is accepted and kept on the entry."""
    flute = instruments.entry('flute')
    tagged = CatalogEntry(
        'test flute',
        'Test flute',
        Family.FLUTES,
        'C4',
        'C7',
        flute.build,
        tags=frozenset({Tag.MECHANICAL}),
    )
    assert tagged.tags == frozenset({Tag.MECHANICAL})


def test_an_alias_finds_its_instrument_in_any_case():
    """An alias resolves to its catalog entry, and get shares the one build."""
    assert instruments.ALIASES['slapstick'] == 'whip'
    assert instruments.entry('Slapstick') is instruments.entry('whip')
    assert instruments.get('SLAPSTICK') is instruments.get('whip')
    assert 'slapstick' not in instruments.names()
    assert 'slapstick' not in [catalog_entry.name for catalog_entry in instruments.entries()]


def test_every_alias_names_one_entry_and_shadows_none():
    """No alias is a catalog name; every alias names an entry; aliases follow the naming rule."""
    for alias, target in instruments.ALIASES.items():
        assert alias not in instruments.CATALOG, alias
        assert target in instruments.CATALOG, (alias, target)


def test_the_alias_table_is_refused_when_it_is_wrong():
    """A bad alias table fails when the catalog is assembled, naming the alias."""
    with pytest.raises(ValueError, match="alias 'flute' is a catalog name"):
        aliases_from({'flute': 'piccolo'}, instruments.CATALOG)
    with pytest.raises(ValueError, match="alias 'fife of doom' names no instrument: 'fyfe'"):
        aliases_from({'fife of doom': 'fyfe'}, instruments.CATALOG)
    with pytest.raises(ValueError, match="alias 'Bad Alias' must be lower-case words"):
        aliases_from({'Bad Alias': 'flute'}, instruments.CATALOG)


def plain_drum(noise: float = 0.5) -> Instrument:
    """A stand-in builder that is a plain function, not a partial.

    Returns:
        The instrument.
    """
    return drum(tones=(Tone(hertz=200.0, ring_seconds=0.2),), noise=noise, tail=0.2)


def sound_alike_table(*extra: CatalogEntry) -> dict[str, CatalogEntry]:
    """A test-only catalog: a parent drum built by a partial, a plain-function drum, and ``extra``.

    Returns:
        Name to entry, as ``catalog_from`` assembles it.
    """
    parent = CatalogEntry(
        'test parent',
        'Test parent',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(drum, tones=(Tone(hertz=200.0, ring_seconds=0.2),), noise=0.5, tail=0.2),
    )
    plain = CatalogEntry(
        'test plain', 'Test plain', Family.DRUMS_AND_PERCUSSION, None, None, plain_drum
    )
    pitched_parent = CatalogEntry(
        'test pitched parent',
        'Test pitched parent',
        Family.PLUCKED_STRINGS,
        'C3',
        'C5',
        plain_drum,
    )
    return catalog_from([(parent, plain, pitched_parent, *extra)])


def unpitched_drum(name: str, **fields) -> CatalogEntry:
    """An unpitched drums and percussion entry named ``name`` with ``fields``.

    Returns:
        The entry.
    """
    return CatalogEntry(name, name.capitalize(), Family.DRUMS_AND_PERCUSSION, None, None, **fields)


def test_an_entry_needs_a_build_or_a_parent():
    """An entry with neither a build nor ``sounds_like`` could make no sound."""
    with pytest.raises(ValueError, match='test nothing: give a build, or the entry it sounds like'):
        unpitched_drum('test nothing')


def test_an_entrys_sound_changes_are_read_only():
    """The changes are copied and frozen: the caller's dict cannot change the entry."""
    changes = {'noise': 0.9}
    alike = unpitched_drum('test alike', sounds_like='test parent', sound_changes=changes)
    changes['noise'] = 0.1
    assert alike.sound_changes == {'noise': 0.9}
    with pytest.raises(TypeError):
        alike.sound_changes['noise'] = 0.2  # pyright: ignore[reportIndexIssue] # ty: ignore[invalid-assignment] - the write is the point


def test_a_pitched_sound_alike_keeps_its_own_range():
    """A sound-alike of a pitched entry builds its parent's sound over its own sourced range."""
    parent = CatalogEntry(
        'test pitched parent',
        'Test pitched parent',
        Family.PLUCKED_STRINGS,
        'C3',
        'C5',
        plain_drum,
    )
    alike = CatalogEntry(
        'test alike',
        'Test alike',
        Family.PLUCKED_STRINGS,
        'E3',
        'E5',
        sounds_like='test pitched parent',
    )

    assembled = sound_alikes_from({parent.name: parent, alike.name: alike})

    assert (assembled['test alike'].lowest, assembled['test alike'].highest) == ('E3', 'E5')
    alike_build = assembled['test alike'].build
    assert alike_build is not None
    assert parent.build is not None
    assert alike_build() == parent.build()


def test_the_sound_alikes_are_refused_when_they_are_wrong():
    """A bad sound-alike fails when the catalog is assembled, naming the entry."""
    refusals = [
        (
            unpitched_drum('test alike', sounds_like='test missing'),
            "test alike: sounds like no instrument: 'test missing'",
        ),
        (unpitched_drum('test alike', sounds_like='test alike'), 'test alike: sounds like itself'),
        (
            unpitched_drum('test alike', sounds_like='test plain', build=plain_drum),
            "test alike: a sound-alike takes the build of 'test plain', not its own",
        ),
        (
            CatalogEntry(
                'test alike',
                'Test alike',
                Family.DRUMS_AND_PERCUSSION,
                'C4',
                'C5',
                sounds_like='test parent',
            ),
            "test alike: pitched exactly when 'test parent' is",
        ),
        (
            CatalogEntry(
                'test alike',
                'Test alike',
                Family.PLUCKED_STRINGS,
                None,
                None,
                sounds_like='test pitched parent',
            ),
            "test alike: pitched exactly when 'test pitched parent' is",
        ),
        (
            unpitched_drum('test alike', build=plain_drum, sound_changes={'noise': 0.9}),
            'test alike: sound changes need the entry it sounds like',
        ),
        (
            unpitched_drum('test alike', sounds_like='test plain', sound_changes={'noise': 0.9}),
            "test alike: sound changes need a functools.partial builder, and 'test plain' has none",
        ),
        (
            unpitched_drum('test alike', sounds_like='test parent', sound_changes={'wobble': 1.0}),
            r"test alike: sound changes \['wobble'\] are not keyword parameters of 'test parent'",
        ),
    ]
    for alike, message in refusals:
        with pytest.raises(ValueError, match=message):
            sound_alikes_from(sound_alike_table(alike))
    first = unpitched_drum('test first', sounds_like='test parent')
    second = unpitched_drum('test second', sounds_like='test first')
    with pytest.raises(ValueError, match="test second: sounds like 'test first', itself a sound"):
        sound_alikes_from(sound_alike_table(first, second))


def test_a_sound_change_cannot_replace_a_positional_argument():
    """A parameter the parent's partial fills positionally is not a keyword it can replace."""
    positional_parent = CatalogEntry(
        'test tom', 'Test tom', Family.DRUMS_AND_PERCUSSION, None, None, partial(plain_drum, 0.3)
    )
    alike = unpitched_drum('test alike', sounds_like='test tom', sound_changes={'noise': 0.9})
    with pytest.raises(ValueError, match=r"sound changes \['noise'\] are not keyword parameters"):
        sound_alikes_from(catalog_from([(positional_parent, alike)]))


def test_a_changed_sound_alike_builds_the_changed_instrument():
    """A sound-alike with a change builds its parent's builder with that keyword replaced."""
    plain_alike = unpitched_drum('test same', sounds_like='test parent')
    changed_alike = unpitched_drum(
        'test changed', sounds_like='test parent', sound_changes={'noise': 0.9}
    )
    assembled = sound_alikes_from(sound_alike_table(plain_alike, changed_alike))
    parent_build = assembled['test parent'].build
    same_build = assembled['test same'].build
    changed_build = assembled['test changed'].build
    assert parent_build is not None and same_build is not None and changed_build is not None
    expected = partial(drum, tones=(Tone(hertz=200.0, ring_seconds=0.2),), noise=0.9, tail=0.2)
    assert changed_build() == expected()
    assert changed_build() != parent_build()
    assert same_build() == parent_build()
    # The entries keep their own names and order, and the rest of the table is unchanged
    assert list(assembled) == [
        'test parent',
        'test plain',
        'test pitched parent',
        'test same',
        'test changed',
    ]
    assert assembled['test changed'].sound_changes == {'noise': 0.9}


def test_an_unknown_name_suggests_aliases_too():
    """A near miss of an alias suggests it."""
    with pytest.raises(KeyError, match='did you mean slapstick'):
        instruments.entry('slapstik')


def test_plucked_idiophones_hold_the_lamellophones_and_music_boxes():
    """Kalimba, mbira and music box moved here by name; the music box plays itself."""
    plucked = instruments.names(family=Family.PLUCKED_IDIOPHONES)
    assert {'kalimba', 'mbira', 'music box', 'sansula'} <= set(plucked)
    moved = {'kalimba', 'mbira', 'music box'}
    assert not moved & set(instruments.names(family=Family.TUNED_PERCUSSION))
    assert instruments.entry('kalimba').playing_range == (Note('C4'), Note('E6'))
    # This lists every mechanical entry, so it grows when another entry is tagged mechanical
    assert instruments.names(tag=Tag.MECHANICAL) == ('music box',)


def test_the_sansula_rings_longer_than_the_kalimba():
    """The sansula ships as its own entry because it rings longer than the kalimba."""
    rendered_note_seconds = 2.5
    onset_window_seconds = 0.05

    def level_after_onset(name: str, *, seconds: float) -> float:
        samples = render_sound(
            spec_for(instruments.get(name), name=name, pitch='C4', length=rendered_note_seconds)
        ).samples
        window = round(onset_window_seconds * SAMPLE_RATE)
        peak = max(
            float(np.sqrt(np.mean(samples[start : start + window] ** 2)))
            for start in range(0, len(samples) - window, window // 5)
        )
        start = round(seconds * SAMPLE_RATE)
        return float(np.sqrt(np.mean(samples[start : start + window] ** 2))) / peak

    assert level_after_onset('sansula', seconds=1.0) > 3 * level_after_onset('kalimba', seconds=1.0)


@pytest.mark.parametrize(
    ('alias', 'target'),
    [
        ('zanza', 'mbira'),
        ('cylinder music box', 'music box'),
        ('disc music box', 'music box'),
        ('wurlitzer electronic piano', 'reed electric piano'),
        ('hohner clavinet', 'clavinet'),
        ('rain box', 'rain machine'),
        ('horse hooves', 'coconut shells'),
        ('dayereh', 'daf'),
        ('ganrang', 'kendang'),
        ('nagara', 'naqareh'),
        ('paila criolla', 'high timbale'),
        ('riq', 'daf'),
        ('naqara', 'naqareh'),
        ('naqqara', 'naqareh'),
        ('tavil', 'thavil'),
        ('chende', 'chenda'),
        ('ganjira', 'kanjira'),
        ('doira', 'daf'),
        ('gran cassa', 'orchestral bass drum'),
        ('bossed gong', 'tuned gong'),
        ('rain stick', 'rainstick'),
        ('sand blocks', 'sandpaper blocks'),
        ('sleigh bells', 'jingle bells'),
        ('chau gong', 'tam tam'),
        ('ugly stick', 'lagerphone'),
        ('monkey stick', 'lagerphone'),
        ('zob stick', 'lagerphone'),
        ('zydeco rubboard', 'frottoir'),
        ('vest frottoir', 'frottoir'),
        ('zatulas', 'washboard'),
        ('zillia', 'finger cymbals'),
        ('zills', 'finger cymbals'),
        ('cencerro', 'cowbell'),
        ('afuche', 'cabasa'),
        ('rumbler', 'contrabass ukulele'),
        ('u bass', 'contrabass ukulele'),
        ('chartar', 'tar'),
        ('chitarrone', 'theorbo'),
        ('hawaiian steel guitar', 'lap steel guitar'),
        ('liuyeqin', 'liuqin'),
        ('neapolitan mandolin', 'mandolin'),
        ('zhongruan', 'ruan'),
        ('piccolo ukulele', 'sopranino ukulele'),
        ('pocket ukulele', 'sopranino ukulele'),
        ('sopranissimo', 'sopranino ukulele'),
        ('taar', 'tar'),
        ('tetrachordo bouzouki', 'greek bouzouki'),
        ('baglama', 'saz'),
        ('bozuk', 'saz'),
        ('outi', 'oud'),
        ('ud', 'oud'),
        ('kanonaki', 'qanun'),
        ('kanun', 'qanun'),
        ('bell lyra', 'glockenspiel'),
        ('boomwhacker', 'boomwhackers'),
        ('saron barung', 'saron'),
        ('orchestra bells', 'glockenspiel'),
        ('chimes', 'tubular bells'),
        ('orchestral chimes', 'tubular bells'),
        ('rin', 'singing bowl'),
        ('soprano steel pan', 'tenor steel pan'),
        ('antique cymbals', 'crotales'),
        ('verrillon', 'glass harp'),
        ('lead pan', 'tenor steel pan'),
        ('ping pong', 'tenor steel pan'),
        ('sanza', 'mbira'),
        ('sansa', 'mbira'),
    ],
)
def test_the_batch_aliases_resolve(alias, target):
    """Each alias is the catalog instrument it names.

    Zanza is the mbira, both music boxes the one comb, the audit's Wurlitzer and Clavinet
    spellings the catalog's, and the rain box and horse hooves the sound effects they name.
    Batch 3's aliases are other names for the same drum or idiophone, which may be a sound-alike
    entry (the rainstick) or in another family (the tuned gong); a distinct instrument that sounds
    like one is its own entry (``test_a_sound_alike_is_listed_and_builds_its_parents_sound``).
    Batch 4's aliases are other names for a plucked instrument (``kanun`` for the qanun, ``bozuk``
    for the saz).
    Batch 5's first half names the glockenspiel two more ways (bell lyra, orchestra bells), the
    tubular bells two more (chimes, orchestral chimes), the saron as the saron barung, and
    the boomwhackers as the boomwhacker.
    Batch 5's second half names the tenor steel pan three more ways (soprano, lead, ping pong),
    the singing bowl as the rin, the crotales as antique cymbals, and across families the glass
    harp as the verrillon and the mbira as the sanza and sansa.
    """
    assert instruments.entry(alias) is instruments.entry(target)


def test_friction_instruments_hold_the_glass_harmonica_glass_harp_and_terpodion():
    """The glass harmonica moved here by name; the glass harp and terpodion are new and swell."""
    friction = set(instruments.names(family=Family.FRICTION_INSTRUMENTS))
    assert {'glass harmonica', 'glass harp', 'terpodion'} <= friction
    # A rubbed singing bowl waits for a sourced range: only the struck bowl is in the catalog
    assert 'rubbed singing bowl' not in instruments.CATALOG
    assert instruments.entry('singing bowl').family == Family.TUNED_PERCUSSION
    assert instruments.entry('glass harmonica').playing_range == (Note('G3'), Note('C6'))
    # Rubbed, not struck: it swells, so its first 50 ms are quieter than its next 150 ms
    entry = instruments.entry('glass harp')
    samples = rendered(instruments.get('glass harp'), pitch=entry.middle_note().name)
    onset = np.max(np.abs(samples[: round(0.05 * SAMPLE_RATE)]))
    held = np.max(np.abs(samples[round(0.05 * SAMPLE_RATE) : round(0.2 * SAMPLE_RATE)]))
    assert onset < held


def test_the_glass_harp_swells_sooner_and_is_brighter_than_the_glass_harmonica():
    """The glass harp ships as its own entry because it sounds unlike the glass harmonica."""
    smoothing_seconds = 0.005

    def seconds_to_ninety_percent(name: str) -> float:
        samples = rendered(instruments.get(name), pitch='G4')
        window = round(smoothing_seconds * SAMPLE_RATE)
        level = np.sqrt(np.convolve(samples**2, np.ones(window) / window, mode='same'))
        return float(np.argmax(level >= 0.9 * np.max(level))) / SAMPLE_RATE

    def spectral_centroid(name: str) -> float:
        samples = rendered(instruments.get(name), pitch='G4')[round(0.2 * SAMPLE_RATE) :]
        magnitudes = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
        frequencies = np.fft.rfftfreq(len(samples), 1 / SAMPLE_RATE)
        return float(np.sum(frequencies * magnitudes) / np.sum(magnitudes))

    assert seconds_to_ninety_percent('glass harp') < seconds_to_ninety_percent('glass harmonica')
    assert seconds_to_ninety_percent('glass harmonica') < seconds_to_ninety_percent('terpodion')
    assert spectral_centroid('glass harp') > spectral_centroid('glass harmonica')
    assert spectral_centroid('terpodion') > spectral_centroid('glass harp')


def test_noise_makers_crack_the_whip():
    """The whip crack is a noise maker; the slapstick whip stayed in drums and percussion."""
    assert instruments.entry('whip crack').family == Family.NOISE_MAKERS
    assert instruments.entry('whip').family == Family.DRUMS_AND_PERCUSSION
    assert not instruments.entry('whip crack').pitched


def test_the_whip_crack_is_sharper_than_the_slapstick_whip():
    """The crack dies away sooner and has more energy high up than the whip, or it is an alias."""
    smoothing_seconds = 0.002

    def seconds_to_one_tenth(samples: np.ndarray) -> float:
        window = round(smoothing_seconds * SAMPLE_RATE)
        level = np.sqrt(np.convolve(samples**2, np.ones(window) / window, mode='same'))
        peak_index = int(np.argmax(level))
        below = np.nonzero(level[peak_index:] < 0.1 * level[peak_index])[0]
        assert below.size > 0, 'the signal never falls below one tenth of its peak'
        return float(below[0]) / SAMPLE_RATE

    def share_of_energy_below(samples: np.ndarray, *, hertz: float) -> float:
        power = np.abs(np.fft.rfft(samples)) ** 2
        frequencies = np.fft.rfftfreq(len(samples), 1 / SAMPLE_RATE)
        return float(np.sum(power[frequencies < hertz]) / np.sum(power))

    crack = rendered(instruments.get('whip crack'), pitch='A4')
    whip = rendered(instruments.get('whip'), pitch='A4')
    assert seconds_to_one_tenth(crack) < seconds_to_one_tenth(whip)
    # The whip's 1 kHz high-pass leaves energy between 1 and 3 kHz that the crack's cuts
    assert share_of_energy_below(crack, hertz=3000.0) < share_of_energy_below(whip, hertz=3000.0)


HELD_SECONDS = 3.0
HORNS = ('diaphone', 'air horn', 'vehicle horn', 'party horn')


def held_level(name: str, *, start_seconds: float) -> float:
    """The RMS level of a 0.1 s window of the entry held for HELD_SECONDS at A4.

    Returns:
        The RMS level.
    """
    samples = render_sound(
        spec_for(instruments.get(name), name=name, pitch='A4', length=HELD_SECONDS)
    ).samples
    start = round(start_seconds * SAMPLE_RATE)
    window = round(0.1 * SAMPLE_RATE)
    return float(np.sqrt(np.mean(samples[start : start + window] ** 2)))


@pytest.mark.parametrize('name', HORNS)
def test_a_horn_sounds_for_as_long_as_it_is_held(name):
    """Held for three seconds, a horn is still sounding at 2.5 s; the whip crack is not."""
    assert held_level(name, start_seconds=2.5) > 0.5 * held_level(name, start_seconds=0.2)


def test_the_whip_crack_is_a_one_shot_however_long_it_is_held():
    """The crack is over by 2.5 s of a three second hold."""
    assert held_level('whip crack', start_seconds=2.5) < 0.01 * held_level(
        'whip crack', start_seconds=0.0
    )


def test_a_tone_with_the_default_sustain_dies_away_as_before():
    """A tone's default sustain is 0 (a drum dies away), and an explicit 0 renders the same."""
    assert Tone(hertz=200.0, ring_seconds=0.3).sustain == 0.0
    default = drum(tones=(Tone(hertz=200.0, ring_seconds=0.3),), noise=0.2)
    explicit = drum(tones=(Tone(hertz=200.0, ring_seconds=0.3, sustain=0.0),), noise=0.2)
    assert np.array_equal(
        rendered(default, pitch='A4', name='default-sustain'),
        rendered(explicit, pitch='A4', name='default-sustain'),
    )
    held = drum(tones=(Tone(hertz=200.0, ring_seconds=0.3, sustain=0.5),))
    assert np.max(np.abs(rendered(held, pitch='A4')[-1000:])) > 0.0


@pytest.mark.parametrize(
    'name', [entry.name for entry in instruments.entries() if not entry.pitched]
)
def test_unpitched_entries_sound_the_same_at_any_pitch(name):
    """An unpitched entry (a drum, an effect) ignores the pitch it is given."""
    instrument = instruments.get(name)
    assert np.array_equal(
        rendered(instrument, pitch='A4', name=name), rendered(instrument, pitch='C2', name=name)
    )


def test_a_name_or_alias_with_a_trailing_newline_is_refused():
    """``$`` alone matches before a final newline; a name must be the whole string."""
    with pytest.raises(ValueError, match='must be lower-case words'):
        CatalogEntry(
            name='fife\n',
            title='Fife',
            family=Family.FLUTES,
            lowest=None,
            highest=None,
            build=lambda: instruments.get('fife'),
        )
    with pytest.raises(ValueError, match='must be lower-case words'):
        aliases_from({'slapstick\n': 'whip'}, instruments.CATALOG)


def test_the_catalog_and_aliases_are_read_only():
    """A write would skip the load-time checks and change every lookup, so both refuse it."""
    with pytest.raises(TypeError):
        instruments.CATALOG['kazoo'] = instruments.entry('flute')  # pyright: ignore[reportIndexIssue] - the write is the point
    with pytest.raises(TypeError):
        instruments.ALIASES['bones'] = 'nope'  # pyright: ignore[reportIndexIssue] - the write is the point


MOVED_TONEWHEEL_ORGANS = (
    'tonewheel organ jazz',
    'tonewheel organ full',
    'tonewheel organ ballad',
    'tonewheel organ rock',
    'tonewheel organ gospel',
    'tonewheel organ percussion second',
    'tonewheel organ percussion third',
)
MOVED_TO_ELECTROMECHANICAL = (
    'tine electric piano',
    'reed electric piano',
    'clavinet',
    *MOVED_TONEWHEEL_ORGANS,
)


def test_electromechanical_holds_the_electric_pianos_clavinet_and_tonewheels():
    """The ten moved entries are electromechanical now, under the same names."""
    electromechanical = set(instruments.names(family=Family.ELECTROMECHANICAL))
    assert set(MOVED_TO_ELECTROMECHANICAL) <= electromechanical
    assert not set(MOVED_TO_ELECTROMECHANICAL) & set(instruments.names(family=Family.KEYBOARDS))
    assert not set(MOVED_TO_ELECTROMECHANICAL) & set(instruments.names(family=Family.ORGANS))
    assert 'combo organ' in instruments.names(family=Family.ORGANS)


# Empty (no cases) when the catalog holds no sound effects; the family is compared as a string
SOUND_EFFECT_NAMES = [
    entry.name for entry in instruments.entries() if entry.family == 'sound effects'
]
# Every catalog entry that a source sets apart from its parent (empty today): it is its own
# sound, so it gets the one-shot checks as the new drums do
CHANGED_SOUND_ALIKE_NAMES = [
    catalog_entry.name for catalog_entry in instruments.entries() if catalog_entry.sound_changes
]
# Batch 3's new entries, in the sheet's order: the membranophones, then the idiophones
NEW_DRUM_NAMES = [
    'bendir',
    'bombo leguero',
    'chenda',
    'daf',
    'dhol',
    'dholak',
    'field drum',
    'gong bass drum',
    'janggu',
    'kanjira',
    'kebero',
    'kendang',
    'kendang ageng',
    'ketipung',
    'khol',
    'lambeg drum',
    'mridangam',
    'naqareh',
    'otsuzumi',
    'pandeiro',
    'piccolo snare',
    'pipe band snare',
    'thavil',
    # The idiophones (hs starting 1), in the sheet's order
    'agung',
    'anvil',
    'bak',
    'daluo',
    'flat ride cymbal',
    'garamut',
    'ghatam',
    'gongue',
    'guira',
    'jing',
    'jingle bells',
    'karkabou',
    'kemanak',
    'khartal',
    'kkwaenggwari',
    'lagerphone',
    'sizzle cymbal',
    'tiger gong',
    'tingsha',
    'udu',
    'washboard',
    'xiaoluo',
]
# Batch 3's sound-alikes and the entry each sounds like, in the sheet's order
SOUND_ALIKE_PARENTS = {
    'alfaia': 'taiko',
    'ashiko': 'djembe tone',
    'atabaque': 'conga',
    'atumpan': 'tumba',
    'bamboula': 'conga',
    'bangu': 'darbuka tek',
    'bata drum': 'conga',
    'bedug': 'orchestral bass drum',
    'bougarabou': 'djembe bass',
    'buk': 'taiko',
    'caixa malacacheta': 'snare drum',
    'candombe drums': 'conga',
    'carimbo': 'tumba',
    'concert tom': 'mid tom',
    'cultrun': 'bodhran',
    'dabakan': 'conga slap',
    'damphu': 'bodhran',
    'davul': 'dhol',
    'dhak': 'dhol',
    'dhimay': 'surdo',
    'dohol': 'dhol',
    'dollu': 'dhol',
    'dunun': 'floor tom',
    'fontomfrom': 'orchestral bass drum',
    'gbedu': 'orchestral bass drum',
    'gome': 'cajon bass',
    'gudugudu': 'high timbale',
    'hira daiko': 'taiko',
    'huehuetl': 'tumba',
    'igba': 'low bongo',
    'jwago': 'taiko',
    'kakko': 'high tom',
    'kendang ciblon': 'kendang',
    'kendang wadon': 'kendang',
    'kenkeni': 'mid tom',
    'klong khaek': 'kendang',
    'kpanlogo': 'conga',
    'kundu': 'conga',
    'kus': 'taiko',
    'madal': 'kendang',
    'maddalam': 'mridangam',
    'makuta': 'conga',
    'marching snare': 'field drum',
    'nagado daiko': 'taiko',
    'ngoma': 'conga',
    'octoban': 'high tom',
    'okedo daiko': 'high tom',
    'pahu': 'tumba',
    'pakhavaj': 'mridangam',
    'pandero jarocho': 'tambourine',
    'parai': 'bodhran',
    'popcorn snare': 'piccolo snare',
    'puniu': 'high bongo',
    'rebana': 'tambourine',
    'repinique': 'high timbale',
    'sabar': 'djembe tone',
    'sakara drum': 'bodhran',
    'samphor': 'kendang',
    'sangban': 'low tom',
    'shime daiko': 'high tom',
    'tabor': 'field drum',
    'tambora': 'conga',
    'tamborim': 'darbuka tek',
    'tan tan': 'surdo',
    'tanggu': 'mid tom',
    'taphon': 'kendang',
    'tar drum': 'frame drum',
    'tarol': 'snare drum',
    'tasha': 'naqareh',
    'tbilat': 'high bongo',
    'thunder drum': 'orchestral bass drum',
    'thunder tube': 'thunder sheet',
    'tifa': 'djembe tone',
    'tombak': 'darbuka doum',
    'trong chau': 'darbuka tek',
    'trong com': 'kendang',
    'tsuri daiko': 'orchestral bass drum',
    'uchiwa daiko': 'bodhran',
    'urumi': 'high tom',
    'zabumba': 'dhol',
    'khanjani': 'daf',
    'tabl': 'dhol',
    'timbal': 'conga',
    'tumbaknari': 'darbuka doum',
    # The idiophones (hs starting 1), in the sheet's order
    'afoxe': 'cabasa',
    'axatse': 'cabasa',
    'bo': 'china cymbal',
    'bones': 'castanets',
    'cata': 'woodblock',
    'caxirola': 'maracas',
    'caxixi': 'maracas',
    'chengila': 'kkwaenggwari',
    'chimta': 'khartal',
    'chuk': 'cajon bass',
    'crash ride cymbal': 'crash cymbal',
    'ekwe': 'temple block',
    'elathalam': 'finger cymbals',
    'eo': 'guiro',
    'esterilla': 'guiro',
    'ferrinho': 'guira',
    'frottoir': 'guira',
    'ganza': 'shaker',
    'ghungroo': 'jingle bells',
    'hosho': 'maracas',
    'hyoshigi': 'claves',
    'ikoro': 'garamut',
    'jam block': 'woodblock',
    'kecer': 'finger cymbals',
    'lummi stick': 'claves',
    'manjira': 'finger cymbals',
    'moktak': 'temple block',
    'paiban': 'bak',
    'quijada': 'vibraslap',
    'rainstick': 'rain machine',
    'reco reco': 'guiro',
    'sandpaper blocks': 'snare brush',
    'sasara': 'bak',
    'semantron': 'garamut',
    'shekere': 'cabasa',
    'shishi odoshi': 'woodblock',
    'shoko': 'kkwaenggwari',
    'sistrum': 'tambourine',
    'slit drum': 'garamut',
    'spoons': 'castanets',
    'stomp box': 'kick drum',
    'swish cymbal': 'sizzle cymbal',
    'teponaztli': 'garamut',
    'triccaballacca': 'khartal',
    'turkish crescent': 'jingle bells',
    'txalaparta': 'garamut',
    'guayo': 'guira',
}
SOUND_ALIKE_NAMES = list(SOUND_ALIKE_PARENTS)

# The least measured margin is the ocean drum's: its second note's energy is 6.76 times its
# single note's tail (the other effects are 17 times or more, and infinite for the three whose
# single note is silent by 0.5 s; of batch 3's drums the gong bass drum, ringing 3 s, is the least
# at 13.5 times, the lambeg drum 397 times, and most are infinite; of its idiophones the tingsha,
# ringing 4 s, is the least at 10.5 times, the tiger gong 13.3 times, and most are infinite, the
# jing excepted below); 3 leaves room without being near 1
SECOND_STRIKE_FACTOR = 3.0
# One-shots whose sourced long ring is still loud when the second note strikes, so the second
# half's energy cannot pass SECOND_STRIKE_FACTOR; each gives its measured ring and why. They still
# must pass the envelope check (``strikes_again``) and the held one-shot test
LONG_RINGING_ONE_SHOTS = {
    'jing': (
        'a 0.5 s note rings 2.18 s to 1% of its peak (a 4 s ring, the source\'s "gentle and'
        ' lingering sound"); at 0.5 s its 205 and 615 Hz partials are half a cycle out of phase'
        ' with the next strike, so the two cancel: the second half holds 1952 of the 4570 energy'
        " units an uncorrelated sum would, an energy share 2.59 times the single note's (the"
        ' envelope check passes by 26.6 times)'
    ),
}
# The envelopes are 20 ms RMS windows over the whole render, each scaled to unit length, so the
# comparison survives each render being normalized to its own peak
ENVELOPE_WINDOW_SECONDS = 0.02
# Measured distances, two notes from one note plus the same note 0.5 s later against two notes
# from one held note (P:1): thunder sheet 0.045 / 0.363, rain machine 0.022 / 0.569, ocean drum
# 0.067 / 0.218, cannon 0.016 / 0.749, crash box 0.018 / 0.757, coconut shells 0.041 / 0.803,
# door slam 0.012 / 0.766, giants footsteps 0.000 / 0.765. Batch 3's drums are all 0.040 or less
# against 0.454 or more (the otsuzumi's 0.040 / 0.802 is their least margin, 19.96 times), and its
# idiophones 0.035 or less against 0.138 or more (the bak's 0.035 / 0.797 is their least margin,
# 22.6 times; the jing's 0.005 / 0.138, 26.6 times). The least margin is the ocean drum's (3.25
# times); 2 keeps room on both sides
RESTRIKE_CLOSER_FACTOR = 2.0
# Held for six seconds, every effect's and drum's ring is long over by 5 s (the ocean drum's 0.8 s
# attack and 2.5 s ring ends by 3.3 s; the gong bass drum's 3 s ring by 3 s; the longest, the
# jing's and tingsha's 4 s rings, by 4 s); measured, every one is exactly silent there
ONE_SHOT_HELD_SECONDS = 6.0
ONE_SHOT_CHECK_SECONDS = 5.0


def test_sound_effects_hold_the_thunder_sheet():
    """The thunder sheet is a sound effect, and it is unpitched."""
    assert instruments.entry('thunder sheet').family == Family.SOUND_EFFECTS
    assert not instruments.entry('thunder sheet').pitched


def second_half_energy_share(samples: np.ndarray, *, length: int) -> float:
    """Energy from 0.5 s to 1.0 s relative to the energy in the first 0.5 s.

    The render is padded with zeros to ``length``. A share survives each render being
    normalized to its own peak.

    Returns:
        The share.
    """
    padded = np.zeros(length)
    padded[: min(len(samples), length)] = samples[:length]
    half = round(0.5 * SAMPLE_RATE)
    return float(np.sum(padded[half : 2 * half] ** 2) / np.sum(padded[:half] ** 2))


def unit_envelope(samples: np.ndarray, *, length: int) -> np.ndarray:
    """The render's RMS level in ENVELOPE_WINDOW_SECONDS windows, scaled to unit length.

    The render is padded with zeros to ``length``.

    Returns:
        The envelope.
    """
    padded = np.zeros(length)
    padded[: min(len(samples), length)] = samples[:length]
    window = round(ENVELOPE_WINDOW_SECONDS * SAMPLE_RATE)
    window_count = length // window
    levels = np.sqrt(np.mean(padded[: window_count * window].reshape(window_count, window) ** 2, 1))
    return levels / np.linalg.norm(levels)


def strikes_again(twice: np.ndarray, *, single: np.ndarray, merged: np.ndarray) -> bool:
    """Whether ``twice`` is two strikes rather than one held note.

    It must be closer, by RESTRIKE_CLOSER_FACTOR, to ``single`` plus ``single`` 0.5 s later
    than to ``merged``, the same notes merged into one held note: a re-strike starts the swell
    again from nothing, or adds a fresh transient, where a held note carries on.

    Returns:
        True for two strikes.
    """
    half = round(0.5 * SAMPLE_RATE)
    length = max(len(twice), len(merged), half + len(single))
    expected = np.zeros(length)
    expected[: len(single)] += single
    expected[half : half + len(single)] += single
    twice_envelope = unit_envelope(twice, length=length)
    to_expected = np.linalg.norm(twice_envelope - unit_envelope(expected, length=length))
    to_merged = np.linalg.norm(twice_envelope - unit_envelope(merged, length=length))
    return bool(RESTRIKE_CLOSER_FACTOR * to_expected < to_merged)


@pytest.mark.parametrize('name', SOUND_EFFECT_NAMES + NEW_DRUM_NAMES + CHANGED_SOUND_ALIKE_NAMES)
def test_a_one_shot_strikes_again_on_each_note(name):
    """A second note adds its own strike, and is not the first note merged into a held one."""
    instrument = instruments.get(name)
    pitch = instruments.entry(name).middle_note().name
    twice = render_sound(spec_for(instrument, name=name, notes=f'{pitch}:0.5 {pitch}:0.5')).samples
    single = render_sound(spec_for(instrument, name=name, notes=f'{pitch}:0.5')).samples
    merged = render_sound(spec_for(instrument, name=name, notes=f'{pitch}:1')).samples
    length = max(len(twice), len(single))
    assert np.max(np.abs(twice)) <= 1.0, name
    if name not in LONG_RINGING_ONE_SHOTS:
        assert second_half_energy_share(twice, length=length) > SECOND_STRIKE_FACTOR * (
            second_half_energy_share(single, length=length)
        ), name
    assert strikes_again(twice, single=single, merged=merged), name


@pytest.mark.parametrize('name', SOUND_EFFECT_NAMES + NEW_DRUM_NAMES + CHANGED_SOUND_ALIKE_NAMES)
def test_a_one_shot_stops_however_long_it_is_held(name):
    """Held for six seconds, a one-shot is far below its loudest by 5 s: none sustains."""
    samples = render_sound(
        spec_for(instruments.get(name), name=name, pitch='A4', length=ONE_SHOT_HELD_SECONDS)
    ).samples
    window = round(0.1 * SAMPLE_RATE)
    window_count = len(samples) // window
    levels = np.sqrt(
        np.mean(samples[: window_count * window].reshape(window_count, window) ** 2, 1)
    )
    late = levels[round(ONE_SHOT_CHECK_SECONDS / 0.1)]
    assert late < 0.01 * np.max(levels), name


def sound_group(name: str) -> str:
    """The name an entry's sound belongs to: an unchanged sound-alike's parent, else its own.

    Returns:
        The name.
    """
    catalog_entry = instruments.entry(name)
    if catalog_entry.sounds_like is not None and not catalog_entry.sound_changes:
        return catalog_entry.sounds_like
    return name


def test_no_two_drums_build_the_same_instrument():
    """Every entry in the family is its own sound (the anti-goal: no renamed copies).

    Only an entry and its unchanged sound-alikes, or two unchanged sound-alikes of one parent,
    may be equal; a sound-alike with changes must differ from every other entry.
    """
    names = instruments.names(family=Family.DRUMS_AND_PERCUSSION)
    same = [
        (first, second)
        for index, first in enumerate(names)
        for second in names[index + 1 :]
        if instruments.get(first) == instruments.get(second)
        and sound_group(first) != sound_group(second)
    ]
    assert same == []


# The 58 plucked strings that predate batch 4: their shared builds predate the anti-goal rule
EXISTING_PLUCKED_NAMES = frozenset({
    'classical guitar',
    'acoustic guitar',
    'twelve string guitar',
    'baritone guitar',
    'resonator guitar',
    'jazz guitar',
    'electric guitar',
    'electric guitar overdrive',
    'electric guitar distortion',
    'lap steel guitar',
    'pedal steel guitar',
    'bass guitar',
    'picked bass',
    'slap bass',
    'fretless bass',
    'five string bass',
    'six string bass',
    'acoustic bass guitar',
    'soprano ukulele',
    'concert ukulele',
    'tenor ukulele',
    'baritone ukulele',
    'banjo',
    'tenor banjo',
    'mandolin',
    'mandola',
    'octave mandolin',
    'mandocello',
    'irish bouzouki',
    'greek bouzouki',
    'lute',
    'archlute',
    'theorbo',
    'baroque guitar',
    'vihuela',
    'cittern',
    'oud',
    'saz',
    'sitar',
    'tanpura',
    'veena',
    'sarod',
    'koto',
    'shamisen',
    'pipa',
    'guzheng',
    'gayageum',
    'balalaika',
    'bass balalaika',
    'domra',
    'charango',
    'cuatro',
    'tres',
    'appalachian dulcimer',
    'zither',
    'autoharp',
    'kantele',
    'psaltery',
})
# Batch 4's entries with their own build, in the sheet's order (the necked lutes and the zither)
NEW_PLUCKED_NAMES = [
    'angelique',
    'banjolele',
    'chapman stick',
    'ruan',
    'tar',
    'tiple colombiano',
    'qanun',
]
# Batch 4's sound-alikes and the entry each sounds like, in the sheet's order
PLUCKED_SOUND_ALIKE_PARENTS = {
    'bass ukulele': 'acoustic bass guitar',
    'contrabass ukulele': 'acoustic bass guitar',
    'bulgarian tambura': 'mandolin',
    'electric bass vi': 'baritone guitar',
    'gaoyin ruan': 'ruan',
    'liuqin': 'pipa',
    'piccolo domra': 'domra',
    'plectrum banjo': 'tenor banjo',
    'requinto guitar': 'classical guitar',
    'daruan': 'ruan',
    'sanxian': 'banjo',
    'secunda balalaika': 'balalaika',
    'setar': 'pipa',
    'seven string guitar': 'electric guitar',
    'sopranino ukulele': 'soprano ukulele',
    'terz guitar': 'classical guitar',
    'trichordo bouzouki': 'greek bouzouki',
    'viola da terra': 'tiple colombiano',
    'xiaoruan': 'ruan',
    'alpine zither': 'zither',
    'five string kantele': 'kantele',
    'gusli': 'kantele',
    'harpejji': 'chapman stick',
    'concert kankles': 'kantele',
    'nigenkin': 'koto',
    'siter': 'appalachian dulcimer',
    'yakumogoto': 'appalachian dulcimer',
}


# The 23 tuned percussion entries that predate batch 5
EXISTING_TUNED_NAMES = frozenset({
    'glockenspiel',
    'crotales',
    'xylophone',
    'marimba',
    'bass marimba',
    'vibraphone',
    'balafon',
    'tubular bells',
    'church bell',
    'carillon',
    'handbells',
    'tenor steel pan',
    'double second steel pan',
    'cello steel pan',
    'bass steel pan',
    'handpan',
    'timpani',
    'saron',
    'gender',
    'bonang',
    'tuned gong',
    'singing bowl',
    'tabla dayan',
})
# Batch 5's tuned percussion: the names of its entries with their own build, and each of its
# sound-alikes with the entry it sounds like
NEW_TUNED_NAMES: list[str] = ['boomwhackers', 'gangsa']
TUNED_SOUND_ALIKE_PARENTS: dict[str, str] = {
    'alto glockenspiel': 'glockenspiel',
    'alto metallophone': 'glockenspiel',
    'alto xylophone': 'xylophone',
    'bass metallophone': 'glockenspiel',
    'bass xylophone': 'xylophone',
    'kantilan': 'gangsa',
    'soprano glockenspiel': 'glockenspiel',
    'soprano metallophone': 'glockenspiel',
    'soprano xylophone': 'xylophone',
    'tubaphone': 'glockenspiel',
    'ugal': 'gangsa',
}

# The 15 electronic entries that predate batch 6
EXISTING_ELECTRONIC_NAMES = frozenset({
    'theremin',
    'ondes martenot',
    'saw lead',
    'square lead',
    'supersaw',
    'synth pad',
    'synth strings',
    'synth brass',
    'synth bass',
    'sub bass',
    'synth pluck',
    'chip square',
    'chip pulse 25',
    'chip pulse 12',
    'chip triangle',
})
# Batch 6's electronic family: the names of its entries with their own build, each of its
# sound-alikes with the entry it sounds like, and the entries that are unpitched (the drum
# machines' voices; Tasks 4 and 6 fill these)
NEW_ELECTRONIC_NAMES: list[str] = []
ELECTRONIC_SOUND_ALIKE_PARENTS: dict[str, str] = {}
ELECTRONIC_UNPITCHED_NAMES: frozenset[str] = frozenset()


class BatchFamily(NamedTuple):
    """A family a batch grew: the entries that predate it, what it added and what is unpitched."""

    existing_names: frozenset[str]
    new_names: list[str]
    sound_alike_parents: dict[str, str]
    unpitched_names: frozenset[str] = frozenset()


BATCH_FAMILIES: dict[Family, BatchFamily] = {
    Family.PLUCKED_STRINGS: BatchFamily(
        EXISTING_PLUCKED_NAMES, NEW_PLUCKED_NAMES, PLUCKED_SOUND_ALIKE_PARENTS
    ),
    Family.ELECTRONIC: BatchFamily(
        EXISTING_ELECTRONIC_NAMES,
        NEW_ELECTRONIC_NAMES,
        ELECTRONIC_SOUND_ALIKE_PARENTS,
        ELECTRONIC_UNPITCHED_NAMES,
    ),
    Family.TUNED_PERCUSSION: BatchFamily(
        EXISTING_TUNED_NAMES, NEW_TUNED_NAMES, TUNED_SOUND_ALIKE_PARENTS
    ),
}


@pytest.mark.parametrize('family', list(BATCH_FAMILIES), ids=str)
def test_no_new_build_is_another_entrys_instrument(family):
    """A batch's build is its own sound (the anti-goal), whatever entry it is set against."""
    new_names = BATCH_FAMILIES[family].new_names
    names = instruments.names(family=family)
    same = [
        (new_name, other)
        for new_name in new_names
        for other in names
        if other != new_name
        and instruments.entry(other).sounds_like is None
        and instruments.get(new_name) == instruments.get(other)
    ]
    assert same == []


@pytest.mark.parametrize('family', list(BATCH_FAMILIES), ids=str)
def test_the_new_entries_are_in_their_family_pitched_unless_listed(family):
    """Each new entry, sound-alikes included, is in its family, pitched unless the row lists it."""
    row = BATCH_FAMILIES[family]
    new_entries = [*row.new_names, *row.sound_alike_parents]
    assert row.unpitched_names <= set(new_entries)
    for name in new_entries:
        assert instruments.entry(name).family == family, name
        assert instruments.entry(name).pitched == (name not in row.unpitched_names), name
    assert set(instruments.names(family=family)) == (
        row.existing_names | set(row.new_names) | set(row.sound_alike_parents)
    )


def test_a_sound_alike_is_listed_and_builds_its_parents_sound():
    """Each sound-alike is a name of its own in its family, building its parent's sound."""
    listed = instruments.names(family=Family.DRUMS_AND_PERCUSSION)
    for name, parent in SOUND_ALIKE_PARENTS.items():
        assert name in listed, name
        assert instruments.entry(name).sounds_like == parent, name
        assert instruments.get(name) == instruments.get(parent), name
    for family, row in BATCH_FAMILIES.items():
        listed_in_family = instruments.names(family=family)
        for name, parent in row.sound_alike_parents.items():
            assert name in listed_in_family, name
            assert instruments.entry(name).sounds_like == parent, name
            assert instruments.get(name) == instruments.get(parent), name
    every_sound_alike = [
        catalog_entry.name
        for catalog_entry in instruments.entries()
        if catalog_entry.sounds_like is not None
    ]
    # The catalog lists families in table order: plucked strings, electronic, tuned percussion,
    # then drums
    assert every_sound_alike == (
        list(PLUCKED_SOUND_ALIKE_PARENTS)
        + list(ELECTRONIC_SOUND_ALIKE_PARENTS)
        + list(TUNED_SOUND_ALIKE_PARENTS)
        + SOUND_ALIKE_NAMES
    )


def test_the_new_drums_are_in_their_family():
    """Each new drum is a drums and percussion entry, unpitched."""
    for name in NEW_DRUM_NAMES:
        assert instruments.entry(name).family == Family.DRUMS_AND_PERCUSSION, name
        assert not instruments.entry(name).pitched, name


def test_the_pianet_settles_from_a_bright_strike():
    """The Pianet's strike has far more energy above its fundamental than its tone 0.3 s on.

    The page (https://en.wikipedia.org/wiki/Hohner_Pianet): "a complex mixture of harmonics when
    the reed is first struck, which later reduces to a cleaner sustained tone". Measured, the
    share of energy above 1.5 times the fundamental is 0.20 in the first 50 ms and 0.0037 from
    0.3 to 0.4 s at B3 (53.7 times), 52.8 times at F1 and 46.8 times at F6; the reed electric
    piano, whose harmonics fall together, measures 0.80 to 0.86 times. 10 is clearly settled.
    """

    def share_above(samples: np.ndarray, *, hertz: float) -> float:
        power = np.abs(np.fft.rfft(samples * np.hanning(len(samples)))) ** 2
        frequencies = np.fft.rfftfreq(len(samples), 1 / SAMPLE_RATE)
        return float(np.sum(power[frequencies > hertz]) / np.sum(power))

    entry = instruments.entry('hohner pianet')
    for note in (entry.middle_note(), Note('F1'), Note('F6')):
        samples = render_sound(
            spec_for(instruments.get(entry.name), name=entry.name, pitch=note.name, length=0.5)
        ).samples
        cutoff = 1.5 * float(note.to_hz())
        strike = share_above(samples[: round(0.05 * SAMPLE_RATE)], hertz=cutoff)
        settled = share_above(
            samples[round(0.3 * SAMPLE_RATE) : round(0.4 * SAMPLE_RATE)], hertz=cutoff
        )
        assert strike > 10.0 * settled, note.name


def test_the_gangsa_pairs_its_fundamental_at_the_ombak_ratio():
    """A gangsa note holds two fundamentals 228 / 220 = 1.036 apart, the pair's ombak.

    The Gamelan gong kebyar page (https://en.wikipedia.org/wiki/Gamelan_gong_kebyar): "one note
    on a female gangsa pemadé might be tuned to 220 Hz, while the male gangsa pemadé might be
    tuned slightly higher to 228 Hz". The spectrum of a C4 note has a strong peak at the
    note's frequency and another at 1.036 times it, with far less between them, so a partial sits
    at the ratio (a single fundamental, as the glockenspiel has, has none there).
    """
    note = Note('C4')
    fundamental = float(note.to_hz())

    def peak_near(name: str, hertz: float) -> float:
        samples = rendered(instruments.get(name), pitch=note.name)[: 2 * SAMPLE_RATE]
        magnitude = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
        frequencies = np.fft.rfftfreq(len(samples), 1 / SAMPLE_RATE)
        return float(np.max(magnitude[np.abs(frequencies - hertz) < 1.0]))

    ombak = peak_near('gangsa', 1.036 * fundamental)
    between = peak_near('gangsa', 1.018 * fundamental)
    assert ombak > 0.5 * peak_near('gangsa', fundamental)
    assert ombak > 3.0 * between
    assert peak_near('glockenspiel', 1.036 * fundamental) < 0.1 * peak_near(
        'glockenspiel', fundamental
    )
