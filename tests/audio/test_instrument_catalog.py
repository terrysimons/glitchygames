"""The instrument catalog: every entry builds, renders across its range and plays its pitch."""

import ast
import csv
from fractions import Fraction
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import numpy as np
import pytest

from glitchygames.audio import instruments
from glitchygames.audio.instrument import Filter, Instrument
from glitchygames.audio.instruments import CatalogEntry, Family, Tag
from glitchygames.audio.instruments.free_reeds import FREE_REED_LEVELS
from glitchygames.audio.instruments.organs import FLUTE_STOP_LEVELS, compound_stop_levels
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
    wave_from_levels,
    with_drones,
)
from glitchygames.audio.instruments.voices import FORMANT_TABLE
from glitchygames.audio.pitch import Note
from glitchygames.audio.render import render_sound
from glitchygames.audio.waves import Wave
from tests.audio.render_specs import SAMPLE_RATE, spec_for

if TYPE_CHECKING:
    from collections.abc import Iterable

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
            'subcontrabass recorder',
        ),
        (
            'soprano trombone',
            'alto trombone',
            'trombone',
            'bass trombone',
            'contrabass trombone',
        ),
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
    hertz = float(note.to_hz()) / (
        2.0 if name in SIXTEEN_FOOT_ORGANS or name in KEYBOARD_SIXTEEN_FOOT_NAMES else 1.0
    )
    hertz *= 8.0 / footage_feet(ORGAN_STOP_FOOTAGES.get(name, '8'))
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
        ('vox continental', 'combo organ'),
        ('thereminvox', 'theremin'),
        ('etherwave', 'theremin'),
        ('chip sawtooth', 'sid sawtooth'),
        ('ym2149', 'ay 3 8910'),
        ('lira korbowa', 'hurdy gurdy'),
        ('soprano viol', 'treble viol'),
        ('behala', 'violin'),
        ('matouqin', 'morin khuur'),
        ('kemence', 'kemenche'),
        ('contralto', 'alto ah'),
        ('boy soprano', 'treble ah'),
        ('penny whistle', 'tin whistle'),
        ('jula jula', 'pan flute'),
        ('julu julu', 'pan flute'),
        ('syrinx', 'pan flute'),
        ('siyotanka', 'native american flute'),
        ('b flat piccolo trumpet', 'piccolo trumpet'),
        ('tenor tuba', 'euphonium'),
        ('treble cornett', 'cornett'),
        ('cornet a pistons', 'cornet'),
        ('tenor horn', 'alto horn'),
        ('zink', 'cornett'),
        ('dung dkar', 'conch'),
        ('hakgediya', 'conch'),
        ('pututu', 'conch'),
        ('shankha', 'conch'),
        ('waldhorn', 'french horn'),
        ('inventionshorn', 'natural horn'),
        ('yidaki', 'didgeridoo'),
        ('mako', 'didgeridoo'),
        ('alpenhorn', 'alphorn'),
        ('fotuto', 'conch'),
        ('cor anglais', 'english horn'),
        ('baritone oboe', 'bass oboe'),
        ('fagott', 'bassoon'),
        ('cervelas', 'rackett'),
        ('gyaling', 'suona'),
        ('zurla', 'zurna'),
        ('bombard', 'bombarde'),
        ('surna', 'zurna'),
        ('surnay', 'zurna'),
        ('zournas', 'zurna'),
        ('haidi', 'suona'),
        ('irish pipes', 'uilleann pipes'),
        ('lowland pipes', 'border pipes'),
        ('half long pipes', 'border pipes'),
        ('gaita galega', 'galician gaita'),
        ('open diapason', 'pipe organ principal'),
        ('organ trompette', 'pipe organ reed'),
        ('air calliope', 'calliope'),
        ('calliaphone', 'calliope'),
        ('fender rhodes', 'tine electric piano'),
        ('richter harmonica', 'harmonica'),
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
    Batch 6's first half names the theremin two more ways (thereminvox, etherwave) and, across
    families, the organs' combo organ as the Vox Continental.
    Batch 6's second half names the SID's sawtooth as the chiptune sawtooth, and the
    AY-3-8910 as Yamaha's licensed YM2149; both targets are sound-alike entries.
    Batch 9's first half names the tin whistle as the penny whistle, and its second half names the
    pan flute as the jula jula, the julu julu and the syrinx and the native american flute as the
    siyotanka.
    Batch 10's first half names the piccolo trumpet as the B-flat piccolo trumpet, the euphonium
    as the tenor tuba, the cornett as the treble cornett and the zink, the cornet as the cornet a
    pistons, and the alto horn as the tenor horn.
    Batch 10's second half names the conch as the dung dkar, the hakgediya, the pututu, the
    shankha and the fotuto, the french horn as the waldhorn, the natural horn as the
    inventionshorn, the didgeridoo as the yidaki and the mako, and the alphorn as the alpenhorn.
    Batch 11's first half names the english horn as the cor anglais, the bass oboe as the baritone
    oboe, the bassoon as the fagott (its German name) and the rackett as the cervelas.
    Batch 11's second half names the suona as the gyaling and the haidi, the zurna as the zurla,
    the surna, the surnay and the zournas, and the bombarde as the bombard.
    Batch 12's bagpipes name the uilleann pipes as the irish pipes, the border pipes as the
    lowland pipes and the half long pipes, and the galician gaita as the gaita galega.
    Batch 13's organ stops name the pipe organ principal as the open diapason (its English name)
    and the pipe organ reed as the organ trompette (the trumpet stop's French name), and its
    organs as instruments name the calliope as the air calliope and the calliaphone.
    Batch 15's pianos name the tine electric piano as the fender rhodes.
    Batch 16's free reeds name the harmonica as the richter harmonica (a Richter layout is a
    tuning, and the catalog's harmonica is the Richter-tuned diatonic in C).
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
# sound, so it gets the one-shot checks as the new drums do. A retuned bagpipe is left out: it
# sustains, so the one-shot checks do not apply; test_a_retuned_bagpipe_sounds_its_sourced_drones
# checks it. A stop at another footage sustains too; test_an_organ_stop_sounds_at_its_footage
# checks it
CHANGED_SOUND_ALIKE_NAMES = [
    catalog_entry.name
    for catalog_entry in instruments.entries()
    if catalog_entry.sound_changes and catalog_entry.family not in {Family.BAGPIPES, Family.ORGANS}
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
# Batch 6's drum-machine voices with their own builds, in the sheet's order. None today: the
# sheet makes every TR-808 voice and the Syndrum a sound-alike of the drum it sounds like
# (plans/data/instrument-audit/batch-6.tsv)
NEW_ELECTRONIC_DRUM_NAMES: list[str] = []
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


@pytest.mark.parametrize(
    'name',
    SOUND_EFFECT_NAMES + NEW_DRUM_NAMES + NEW_ELECTRONIC_DRUM_NAMES + CHANGED_SOUND_ALIKE_NAMES,
)
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


@pytest.mark.parametrize(
    'name',
    SOUND_EFFECT_NAMES + NEW_DRUM_NAMES + NEW_ELECTRONIC_DRUM_NAMES + CHANGED_SOUND_ALIKE_NAMES,
)
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
# machines' voices). The sheet's two noise rows, nes noise and game boy
# short noise, wait for a fixed noise clock: the engine scales an all-noise instrument's LFSR
# clock by the pitch it is played at (build_spec's unpitched_scale), so neither would ignore the
# pitch as an unpitched entry must (test_unpitched_entries_sound_the_same_at_any_pitch)
NEW_ELECTRONIC_NAMES: list[str] = ['nes triangle']
ELECTRONIC_SOUND_ALIKE_PARENTS: dict[str, str] = {
    'ay 3 8910': 'chip square',
    'electronic clave': 'claves',
    'electronic conga': 'electronic kick',
    'electronic cowbell': 'cowbell',
    'electronic maracas': 'maracas',
    'electronic tom': 'electronic kick',
    'pc speaker': 'chip square',
    'sid sawtooth': 'saw lead',
    'sn76489': 'chip square',
    'syndrum': 'electronic kick',
}
ELECTRONIC_UNPITCHED_NAMES: frozenset[str] = frozenset({
    'electronic clave',
    'electronic conga',
    'electronic cowbell',
    'electronic maracas',
    'electronic tom',
    'syndrum',
})


# The 30 flutes that predate batch 9: their shared builds predate the anti-goal rule
EXISTING_FLUTE_NAMES = frozenset({
    'piccolo',
    'flute',
    'alto flute',
    'bass flute',
    'contra alto flute',
    'contrabass flute',
    'wooden flute',
    'wooden concert flute',
    'baroque flute',
    'fife',
    'tin whistle',
    'low whistle',
    'sopranino recorder',
    'soprano recorder',
    'alto recorder',
    'tenor recorder',
    'bass recorder',
    'great bass recorder',
    'contrabass recorder',
    'pan flute',
    'shakuhachi',
    'bansuri',
    'dizi',
    'xiao',
    'quena',
    'ney',
    'kaval',
    'native american flute',
    'ocarina',
    'bass ocarina',
})
# Batch 9's flutes with their own build, in the sheet's order. None: every row the sheet
# ships is a sound-alike (plans/data/instrument-audit/batch-9.tsv)
NEW_FLUTE_NAMES: list[str] = []
# Batch 9's flute sound-alikes and the entry each sounds like, in the sheet's order
FLUTE_SOUND_ALIKE_PARENTS: dict[str, str] = {
    'csakan': 'soprano recorder',
    'subcontrabass recorder': 'contrabass recorder',
    'ryuteki': 'bansuri',
}
# Batch 9's flutes that are unpitched (a whistle its source calls noise), in the sheet's order
FLUTE_UNPITCHED_NAMES: frozenset[str] = frozenset()


# The 9 clarinets that predate batch 14: their shared builds predate the anti-goal rule
EXISTING_CLARINET_NAMES: frozenset[str] = frozenset({
    'e flat clarinet',
    'clarinet',
    'a clarinet',
    'basset horn',
    'alto clarinet',
    'bass clarinet',
    'contra alto clarinet',
    'contrabass clarinet',
    'chalumeau',
})
# Batch 14's clarinets with their own build, in the sheet's order
# (plans/data/instrument-audit/batch-14.tsv)
NEW_CLARINET_NAMES: list[str] = []
# Batch 14's clarinet sound-alikes and the entry each sounds like, in the sheet's order
CLARINET_SOUND_ALIKE_PARENTS: dict[str, str] = {'c clarinet': 'clarinet'}


# The 23 double reeds that predate batch 11: their shared builds predate the anti-goal rule
EXISTING_DOUBLE_REED_NAMES: frozenset[str] = frozenset({
    'oboe',
    'oboe d amore',
    'english horn',
    'bass oboe',
    'heckelphone',
    'bassoon',
    'contrabassoon',
    'sarrusophone',
    'soprano shawm',
    'alto shawm',
    'tenor shawm',
    'bass shawm',
    'suona',
    'zurna',
    'bombarde',
    'hichiriki',
    'piri',
    'soprano crumhorn',
    'alto crumhorn',
    'tenor crumhorn',
    'bass crumhorn',
    'rackett',
    'duduk',
})
# Batch 11's double reeds with their own build, in the sheet's order. None: every row the sheet
# ships is a sound-alike (plans/data/instrument-audit/batch-11.tsv)
NEW_DOUBLE_REED_NAMES: list[str] = []
# Batch 11's double reed sound-alikes and the entry each sounds like, in the sheet's order
DOUBLE_REED_SOUND_ALIKE_PARENTS: dict[str, str] = {
    'contraforte': 'contrabassoon',
    'piccolo heckelphone': 'heckelphone',
}


# The 8 bagpipes that predate batch 12: their shared builds predate the anti-goal rule
EXISTING_BAGPIPE_NAMES: frozenset[str] = frozenset({
    'highland bagpipe',
    'uilleann pipes',
    'scottish smallpipes',
    'border pipes',
    'northumbrian smallpipes',
    'galician gaita',
    'bulgarian gaida',
    'musette de cour',
})
# Batch 12's bagpipes with their own build, in the sheet's order
# (plans/data/instrument-audit/batch-12.tsv)
NEW_BAGPIPE_NAMES: list[str] = ['sackpipa']
# Batch 12's bagpipe sound-alikes and the entry each sounds like, in the sheet's order (none yet)
BAGPIPE_SOUND_ALIKE_PARENTS: dict[str, str] = {}
# Batch 12's bagpipe sound-alikes whose sourced drones differ from their parent's, with their
# drone notes (sounding, highest first), in the sheet's order: each is built with
# sound_changes={'drones': ...} (plans/data/instrument-audit/batch-12.tsv)
BAGPIPE_RETUNED_DRONES: dict[str, tuple[str, ...]] = {}


# The 9 organs that predate batch 13: their shared builds predate the anti-goal rule
EXISTING_ORGAN_NAMES: frozenset[str] = frozenset({
    'pipe organ principal',
    'pipe organ flute',
    'pipe organ reed',
    'pipe organ string',
    'pipe organ plenum',
    'positive organ',
    'combo organ',
    'theatre organ',
    'calliope',
})
# Batch 13's organs with their own build, in the sheet's order
# (plans/data/instrument-audit/batch-13.tsv)
NEW_ORGAN_NAMES: list[str] = ['cornet organ', 'organ clarinet', 'stopped diapason']
# Batch 13's organ sound-alikes and the entry each sounds like, in the sheet's order
ORGAN_SOUND_ALIKE_PARENTS: dict[str, str] = {
    'bourdon': 'stopped diapason',
    'organ krummhorn': 'organ clarinet',
    'organ oboe': 'pipe organ reed',
    'organ tuba': 'pipe organ reed',
    'posthorn': 'pipe organ reed',
    'salicional': 'pipe organ string',
    'voix celeste': 'pipe organ string',
}
# Batch 13's organ entries that sound at a footage other than 8' (a one-rank stop, through
# _pipe_stop's footage), with the footage as the sheet writes it: the range is the keys at 8'
# pitch and the stop sounds 12 x log2(8 / footage) semitones from them
# (plans/data/instrument-audit/batch-13.tsv)
ORGAN_STOP_FOOTAGES: dict[str, str] = {'bourdon': '16'}
# Batch 13's self-playing organs (Tag.MECHANICAL), in catalog order: the builds, then the
# sound-alikes, each in the sheet's order (plans/data/instrument-audit/batch-13.tsv)
MECHANICAL_ORGAN_NAMES: list[str] = []


# The 11 keyboards that predate batch 15: their shared builds predate the anti-goal rule
EXISTING_KEYBOARD_NAMES: frozenset[str] = frozenset({
    'grand piano',
    'bright grand piano',
    'upright piano',
    'honky tonk piano',
    'fortepiano',
    'harpsichord',
    'harpsichord lute stop',
    'virginal',
    'clavichord',
    'celesta',
    'toy piano',
})
# Batch 15's keyboards with their own build, in the sheet's order
# (plans/data/instrument-audit/batch-15.tsv)
NEW_KEYBOARD_NAMES: list[str] = []
# Batch 15's keyboard sound-alikes and the entry each sounds like, in the sheet's order
KEYBOARD_SOUND_ALIKE_PARENTS: dict[str, str] = {}
# Batch 15's self-playing keyboards (Tag.MECHANICAL), in catalog order: the builds, then the
# sound-alikes, each in the sheet's order (plans/data/instrument-audit/batch-15.tsv)
MECHANICAL_KEYBOARD_NAMES: list[str] = []


# The 13 free reeds that predate batch 16: their shared builds predate the anti-goal rule
EXISTING_FREE_REED_NAMES: frozenset[str] = frozenset({
    'accordion',
    'musette accordion',
    'accordion bass',
    'bandoneon',
    'concertina',
    'harmonium',
    'harmonica',
    'chromatic harmonica',
    'bass harmonica',
    'soprano melodica',
    'alto melodica',
    'bass melodica',
    'sheng',
})
# Batch 16's free reeds with their own build, in the sheet's order
# (plans/data/instrument-audit/batch-16.tsv)
NEW_FREE_REED_NAMES: list[str] = []
# Batch 16's free reed sound-alikes and the entry each sounds like, in the sheet's order
FREE_REED_SOUND_ALIKE_PARENTS: dict[str, str] = {}
# Batch 16's self-playing free reeds (Tag.MECHANICAL), in catalog order: the builds, then the
# sound-alikes, each in the sheet's order (plans/data/instrument-audit/batch-16.tsv)
MECHANICAL_FREE_REED_NAMES: list[str] = []


# The 7 harps that predate batch 17: their shared builds predate the anti-goal rule
EXISTING_HARP_NAMES: frozenset[str] = frozenset({
    'concert harp',
    'celtic harp',
    'wire strung harp',
    'triple harp',
    'lyre',
    'kora',
    'harp guitar',
})
# Batch 17's harps with their own build, in the sheet's order
# (plans/data/instrument-audit/batch-17.tsv)
NEW_HARP_NAMES: list[str] = []
# Batch 17's harp sound-alikes and the entry each sounds like, in the sheet's order
HARP_SOUND_ALIKE_PARENTS: dict[str, str] = {}


# The 42 brass instruments that predate batch 10: their shared builds predate the anti-goal rule
EXISTING_BRASS_NAMES: frozenset[str] = frozenset({
    'piccolo trumpet',
    'trumpet',
    'c trumpet',
    'd trumpet',
    'bass trumpet',
    'trumpet straight mute',
    'trumpet cup mute',
    'trumpet harmon mute',
    'cornet',
    'soprano cornet',
    'flugelhorn',
    'bugle',
    'post horn',
    'french horn',
    'descant horn',
    'french horn stopped',
    'natural horn',
    'wagner tuba',
    'mellophone',
    'alto horn',
    'baritone horn',
    'euphonium',
    'alto trombone',
    'trombone',
    'bass trombone',
    'contrabass trombone',
    'trombone cup mute',
    'trombone plunger',
    'sackbut',
    'cimbasso',
    'f tuba',
    'e flat tuba',
    'tuba',
    'sousaphone',
    'cornett',
    'serpent',
    'ophicleide',
    'alphorn',
    'shofar',
    'conch',
    'didgeridoo',
    'vuvuzela',
})
# Batch 10's brass with its own build, in the sheet's order. None: every row the sheet
# ships is a sound-alike (plans/data/instrument-audit/batch-10.tsv)
NEW_BRASS_NAMES: list[str] = []
# Batch 10's brass sound-alikes and the entry each sounds like, in the sheet's order
BRASS_SOUND_ALIKE_PARENTS: dict[str, str] = {
    'bass wagner tuba': 'wagner tuba',
    'soprano trombone': 'trumpet',
}


# The 27 bowed strings that predate batch 7: their shared builds predate the anti-goal rule
EXISTING_BOWED_NAMES = frozenset({
    'violin',
    'viola',
    'cello',
    'double bass',
    'five string double bass',
    'violin section',
    'viola section',
    'cello section',
    'double bass section',
    'violin pizzicato',
    'viola pizzicato',
    'cello pizzicato',
    'double bass pizzicato',
    'violin sul ponticello',
    'fiddle',
    'hardanger fiddle',
    'treble viol',
    'tenor viol',
    'bass viol',
    'violone',
    'viola d amore',
    'nyckelharpa',
    'erhu',
    'morin khuur',
    'sarangi',
    'kemenche',
    'hurdy gurdy',
})
# Batch 7's entries with their own build, in the sheet's order. None: every row the sheet
# ships is a sound-alike (plans/data/instrument-audit/batch-7.tsv)
NEW_BOWED_NAMES: list[str] = []
# Batch 7's sound-alikes and the entry each sounds like, in the sheet's order
BOWED_SOUND_ALIKE_PARENTS: dict[str, str] = {
    'bowed psaltery': 'violin',
    'viola pomposa': 'viola',
}


# The 68 voices and choirs that predate batch 8: their shared builds predate the anti-goal rule
EXISTING_VOICE_NAMES = frozenset(
    {
        f'{voice} {sound}'
        for voice in (
            'soprano',
            'mezzo soprano',
            'alto',
            'treble',
            'countertenor',
            'tenor',
            'baritone',
            'bass',
            'basso profundo',
        )
        for sound in ('ah', 'eh', 'ee', 'oh', 'oo', 'hum')
    }
    | {'whistling'}
)
EXISTING_CHOIR_NAMES = frozenset(
    {
        f'choir {part} {sound}'
        for part in ('soprano', 'alto', 'tenor', 'bass')
        for sound in ('ah', 'oh', 'oo')
    }
    | {'childrens choir'}
)
# Batch 8's voices with their own build, in the sheet's order. Empty until the sheet's rows
# are coded (plans/data/instrument-audit/batch-8.tsv)
NEW_VOICE_NAMES: list[str] = []
# Batch 8's voice sound-alikes and the entry each sounds like, in the sheet's order
VOICE_SOUND_ALIKE_PARENTS: dict[str, str] = {'basso buffo ah': 'bass ah'}
# Batch 8's choirs with their own build, in the sheet's order
NEW_CHOIR_NAMES: list[str] = []
# Batch 8's choir sound-alikes and the entry each sounds like, in the sheet's order
CHOIR_SOUND_ALIKE_PARENTS: dict[str, str] = {}


class BatchFamily(NamedTuple):
    """A family a batch grew: the entries that predate it, what it added and what is unpitched."""

    existing_names: frozenset[str]
    new_names: list[str]
    sound_alike_parents: dict[str, str]
    unpitched_names: frozenset[str] = frozenset()


BATCH_FAMILIES: dict[Family, BatchFamily] = {
    Family.FLUTES: BatchFamily(
        EXISTING_FLUTE_NAMES,
        NEW_FLUTE_NAMES,
        FLUTE_SOUND_ALIKE_PARENTS,
        FLUTE_UNPITCHED_NAMES,
    ),
    Family.CLARINETS: BatchFamily(
        EXISTING_CLARINET_NAMES, NEW_CLARINET_NAMES, CLARINET_SOUND_ALIKE_PARENTS
    ),
    Family.DOUBLE_REEDS: BatchFamily(
        EXISTING_DOUBLE_REED_NAMES, NEW_DOUBLE_REED_NAMES, DOUBLE_REED_SOUND_ALIKE_PARENTS
    ),
    Family.BAGPIPES: BatchFamily(
        EXISTING_BAGPIPE_NAMES, NEW_BAGPIPE_NAMES, BAGPIPE_SOUND_ALIKE_PARENTS
    ),
    Family.FREE_REEDS: BatchFamily(
        EXISTING_FREE_REED_NAMES, NEW_FREE_REED_NAMES, FREE_REED_SOUND_ALIKE_PARENTS
    ),
    Family.BRASS: BatchFamily(EXISTING_BRASS_NAMES, NEW_BRASS_NAMES, BRASS_SOUND_ALIKE_PARENTS),
    Family.BOWED_STRINGS: BatchFamily(
        EXISTING_BOWED_NAMES, NEW_BOWED_NAMES, BOWED_SOUND_ALIKE_PARENTS
    ),
    Family.PLUCKED_STRINGS: BatchFamily(
        EXISTING_PLUCKED_NAMES, NEW_PLUCKED_NAMES, PLUCKED_SOUND_ALIKE_PARENTS
    ),
    Family.HARPS: BatchFamily(EXISTING_HARP_NAMES, NEW_HARP_NAMES, HARP_SOUND_ALIKE_PARENTS),
    Family.KEYBOARDS: BatchFamily(
        EXISTING_KEYBOARD_NAMES, NEW_KEYBOARD_NAMES, KEYBOARD_SOUND_ALIKE_PARENTS
    ),
    Family.ORGANS: BatchFamily(EXISTING_ORGAN_NAMES, NEW_ORGAN_NAMES, ORGAN_SOUND_ALIKE_PARENTS),
    Family.ELECTRONIC: BatchFamily(
        EXISTING_ELECTRONIC_NAMES,
        NEW_ELECTRONIC_NAMES,
        ELECTRONIC_SOUND_ALIKE_PARENTS,
        ELECTRONIC_UNPITCHED_NAMES,
    ),
    Family.TUNED_PERCUSSION: BatchFamily(
        EXISTING_TUNED_NAMES, NEW_TUNED_NAMES, TUNED_SOUND_ALIKE_PARENTS
    ),
    Family.VOICES: BatchFamily(EXISTING_VOICE_NAMES, NEW_VOICE_NAMES, VOICE_SOUND_ALIKE_PARENTS),
    Family.CHOIRS: BatchFamily(EXISTING_CHOIR_NAMES, NEW_CHOIR_NAMES, CHOIR_SOUND_ALIKE_PARENTS),
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


# Every sound-chip voice, in catalog order (Tag.CHIP; batch 6)
CHIP_NAMES = [
    'chip square',
    'chip pulse 25',
    'chip pulse 12',
    'chip triangle',
    'nes triangle',
    'ay 3 8910',
    'pc speaker',
    'sid sawtooth',
    'sn76489',
]


def test_the_chip_tag_marks_exactly_the_sound_chip_voices():
    """names(tag=Tag.CHIP) is every sound-chip voice, each in the electronic family."""
    assert instruments.names(tag=Tag.CHIP) == tuple(CHIP_NAMES)
    assert instruments.names(tag='Chip') == tuple(CHIP_NAMES)
    for name in CHIP_NAMES:
        assert instruments.entry(name).family == Family.ELECTRONIC, name


def test_the_nes_triangle_buzzes_from_its_thirty_two_steps():
    """The NES triangle's 32-step staircase buzzes at harmonics 31 and 33; a smooth one does not.

    NESdev (https://www.nesdev.org/wiki/APU_Triangle): "The sequencer sends the following looping
    32-step sequence of 4-bit values to the mixer", 15 down to 0 and back up to 15. A wave held
    on 32 steps per cycle has images of its fundamental at harmonics 32 - 1 and 32 + 1, each
    about 1/31 of it; a smooth triangle's 31st and 33rd harmonics are 1/31 squared and 1/33
    squared. A 16-step staircase would instead buzz at harmonics 15 and 17, so those stay low
    here. Measured at A2, the stepped wave's are 0.032 and 0.030 of its fundamental and the
    chip triangle's 0.00104 and 0.00092 (31 and 33 times less); 10 keeps room. The Ricoh 2A03
    page's "an overtone is created four octaves higher" is not what the sequence makes: it is
    half-wave antisymmetric (each value 16 steps on is 15 minus it), so it has no even
    harmonics, and its 16th measures 0.
    """
    note = Note('A2')
    hertz = float(note.to_hz())

    def relative_harmonics(name: str) -> list[float]:
        samples = render_sound(
            spec_for(instruments.get(name), name=name, pitch=note.name, length=1.0)
        ).samples
        held = samples[round(0.1 * SAMPLE_RATE) : round(0.9 * SAMPLE_RATE)]
        magnitude = np.abs(np.fft.rfft(held * np.hanning(len(held))))
        frequencies = np.fft.rfftfreq(len(held), 1 / SAMPLE_RATE)
        peaks = [
            float(np.max(magnitude[np.abs(frequencies - harmonic * hertz) < hertz / 4.0]))
            for harmonic in (1, 15, 17, 31, 33)
        ]
        return [peak / peaks[0] for peak in peaks[1:]]

    stepped = relative_harmonics('nes triangle')
    smooth = relative_harmonics('chip triangle')
    stepped_low_harmonics, stepped_image_harmonics = stepped[:2], stepped[2:]
    smooth_image_harmonics = smooth[2:]
    for stepped_level, smooth_level in zip(
        stepped_image_harmonics, smooth_image_harmonics, strict=True
    ):
        assert stepped_level > 10.0 * smooth_level
    # A 16-step staircase would put about 1/15 of the fundamental at harmonics 15 and 17
    for stepped_level in stepped_low_harmonics:
        assert stepped_level < 0.01


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
            if instruments.entry(name).sound_changes:
                assert instruments.get(name) != instruments.get(parent), name
            else:
                assert instruments.get(name) == instruments.get(parent), name
    every_sound_alike = [
        catalog_entry.name
        for catalog_entry in instruments.entries()
        if catalog_entry.sounds_like is not None
    ]
    # The catalog lists families in table order: flutes, clarinets, double reeds, bagpipes, free
    # reeds, brass, bowed strings, plucked strings, harps, keyboards, organs, electronic, tuned
    # percussion, drums, voices, then choirs, as registry.FAMILY_TABLES lists them
    assert every_sound_alike == (
        list(FLUTE_SOUND_ALIKE_PARENTS)
        + list(CLARINET_SOUND_ALIKE_PARENTS)
        + list(DOUBLE_REED_SOUND_ALIKE_PARENTS)
        + list(BAGPIPE_SOUND_ALIKE_PARENTS)
        + list(FREE_REED_SOUND_ALIKE_PARENTS)
        + list(BRASS_SOUND_ALIKE_PARENTS)
        + list(BOWED_SOUND_ALIKE_PARENTS)
        + list(PLUCKED_SOUND_ALIKE_PARENTS)
        + list(HARP_SOUND_ALIKE_PARENTS)
        + list(KEYBOARD_SOUND_ALIKE_PARENTS)
        + list(ORGAN_SOUND_ALIKE_PARENTS)
        + list(ELECTRONIC_SOUND_ALIKE_PARENTS)
        + list(TUNED_SOUND_ALIKE_PARENTS)
        + SOUND_ALIKE_NAMES
        + list(VOICE_SOUND_ALIKE_PARENTS)
        + list(CHOIR_SOUND_ALIKE_PARENTS)
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


# Entries that imitate or omit a feature the engine lacks (sympathetic strings by a detuned copy,
# a buzzing bridge by drive, or no membrane at all). They predate decision 4 and stay, but
# nothing new shares their sound: batch 4's sitar ruling, batch 7's for the bowed ones, and
# batch 9's for the dizi, built without the membrane its page names
# (https://en.wikipedia.org/wiki/Dizi_(instrument): 'adding harmonics to give the final tone a
# buzzing, nasal quality'), and batch 10's for the didgeridoo, built without the moving formants
# its page names (https://en.wikipedia.org/wiki/Didgeridoo: 'These formants, and especially their
# variation during the inhalation and exhalation phases of circular breathing, give the
# instrument its readily recognisable sound.'), and batch 11's for the piri, built as a conical
# shawm though its page says (https://en.wikipedia.org/wiki/Piri_(instrument)): 'It has a
# cylindrical bore.', and batch 12's for the scottish smallpipes, built with an every-harmonic
# chanter though the Bagpipe Society's guide says
# (https://www.bagpipesociety.org.uk/guide/scottish-smallpipes/): 'With its cylindrical bore, the
# sound is characteristically lilting'
APPROXIMATING_NAMES = frozenset({
    'sitar',
    'tanpura',
    'veena',
    'sarod',
    'sarangi',
    'hardanger fiddle',
    'viola d amore',
    'nyckelharpa',
    'hurdy gurdy',
    'dizi',
    'didgeridoo',
    'piri',
    'scottish smallpipes',
})


def test_no_sound_alike_shares_an_approximated_sound():
    """No sound-alike takes the build of an entry that imitates or omits a missing feature."""
    parents = {catalog_entry.sounds_like for catalog_entry in instruments.entries()}
    assert parents & APPROXIMATING_NAMES == set()
    assert set(instruments.names()).issuperset(APPROXIMATING_NAMES)


# The spec's "What the engine cannot make yet": "moving formants, vowel glides, vibrato |
# overtone and throat singing, talk box, vocoder, yodel". Nothing in that row ships under its
# name or an alias until the engine has the feature (decision 4; batch 8). The set holds every
# name batch 8's sheet (plans/data/instrument-audit/batch-8.tsv) held back for moving formants:
# the WAIT rows whose waits_for is "moving formants" and the alias spellings that wait for one of
# them ("its target, khoomei", "its target, yodel" and so on), beside the spec's own names. The
# test below matches these names exactly: it does not catch a qualified name such as "khoomei
# voice"
MOVING_FORMANT_NAMES = frozenset({
    'khoomei',
    'sygyt',
    'kargyraa',
    'borbangnadyr',
    'ezengileer',
    'chylandyk',
    'dumchuktaar',
    'byrlang',
    'tibetan chant',
    'umngqokolo',
    'katajjaq',
    'rekuhkara',
    'yodel',
    'tuvan ensemble',
    'electrolarynx',
    'khoomii',
    'xoomei',
    'overtone singing',
    'harmonic singing',
    'khargyraa',
    'inuit throat singing',
    'iirngaaq',
    'piqqusiraarniq',
    'qiarvaaqtuq',
    'nipaquhiit',
    'jodel',
    'artificial larynx',
    'talk box',
    'sonovox',
    'vocoder',
    'vocoder voice',
    'voder',
})


def test_nothing_waiting_for_moving_formants_is_listed():
    """No catalog name or alias is an instrument the spec holds back for moving formants."""
    assert MOVING_FORMANT_NAMES & set(instruments.names()) == set()
    assert MOVING_FORMANT_NAMES & set(instruments.ALIASES) == set()


# The slide whistle's sound is its glide between notes, which the engine cannot make (it has one
# glide per note and no LFO): it and its names wait for a pitch LFO (portamento between notes),
# batch 4's dan bau ruling (decision 4; batch 9). The test matches exact names, in the catalog or
# the aliases, and the set holds every name plans/data/instrument-audit/batch-9.tsv held back for
# portamento: the slide whistle, its four other names (swanee whistle, lotus flute, piston flute,
# jazz flute; https://en.wikipedia.org/wiki/Slide_whistle), the singing bird box (a piston pipe
# moved along by a cam) and the whistling vessel (its pitch moves as the vessel tilts)
PORTAMENTO_NAMES = frozenset({
    'slide whistle',
    'swanee whistle',
    'lotus flute',
    'piston flute',
    'jazz flute',
    'singing bird box',
    'whistling vessel',
})


def test_nothing_waiting_for_a_glide_between_notes_is_listed():
    """No catalog name or alias is an instrument held back for a glide between notes."""
    assert PORTAMENTO_NAMES & set(instruments.names()) == set()
    assert PORTAMENTO_NAMES & set(instruments.ALIASES) == set()


# Every name plans/data/instrument-audit/batch-10.tsv holds back for an engine feature or a build
# of its own, with its waits_for: the WAIT rows whose reason is not "a sourced range", and the
# alias rows that wait for one of them, in the sheet's order. None ships under that name or as an
# alias until the engine or the build exists (decision 4; batch 10). The test matches exact names
BRASS_HELD_BACK: dict[str, str] = {
    'bazooka': 'moving formants',
    'didjeribone': 'moving formants',
    'subcontrabass tuba': 'sub-audio fundamentals',
    'sudrophone': 'a buzzing membrane',
    'tenor cornett': 'its own build',
    'vienna horn': 'its own build',
}


def test_no_brass_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a brass instrument the sheet holds back for a feature."""
    assert set(BRASS_HELD_BACK) & set(instruments.names()) == set()
    assert set(BRASS_HELD_BACK) & set(instruments.ALIASES) == set()


# Every name plans/data/instrument-audit/batch-11.tsv holds back for an engine feature or a build
# of its own, with its waits_for: the WAIT rows whose reason is not "a sourced range", and the
# alias rows that wait for one of them, in the sheet's order. None ships under that name or as an
# alias until the engine or the build exists (decision 4; batch 11). The test matches exact names
DOUBLE_REED_HELD_BACK: dict[str, str] = {
    'aulos': 'a sourced drone tuning',
    'balaban': 'its own build (a cylindrical bore)',
}


def test_no_double_reed_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a double reed the sheet holds back for a feature."""
    assert set(DOUBLE_REED_HELD_BACK) & set(instruments.names()) == set()
    assert set(DOUBLE_REED_HELD_BACK) & set(instruments.ALIASES) == set()


# Every name plans/data/instrument-audit/batch-12.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, a sourced
# drone tuning or a sourced chanter bore, and the alias rows that wait for one of them, in the
# sheet's order. None ships under that name or as an alias until the reason is met (decision 4;
# batch 12). The test matches exact names
BAGPIPE_HELD_BACK: dict[str, str] = {}


def test_no_bagpipe_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a bagpipe the sheet holds back."""
    assert set(BAGPIPE_HELD_BACK) & set(instruments.names()) == set()
    assert set(BAGPIPE_HELD_BACK) & set(instruments.ALIASES) == set()


def test_a_retuned_bagpipe_sounds_its_sourced_drones():
    """A bagpipe sound-alike in another tuning sounds its own drones, equal-tempered.

    Decision 8's sound_changes: only the drones change, each at its sourced note (A4 = 440 Hz,
    two decimals, as the catalog's builds write hertz), so it differs from its parent.
    """
    retuned = [
        catalog_entry.name
        for catalog_entry in instruments.entries(family=Family.BAGPIPES)
        if catalog_entry.sound_changes
    ]
    assert retuned == list(BAGPIPE_RETUNED_DRONES)
    for name, drone_notes in BAGPIPE_RETUNED_DRONES.items():
        catalog_entry = instruments.entry(name)
        assert set(catalog_entry.sound_changes) == {'drones'}, name
        drone_hertz = [
            float(source.pitch)
            for source_name, source in instruments.get(name).sources
            if source_name.startswith('drone_')
        ]
        assert drone_hertz == [round(float(Note(note).to_hz()), 2) for note in drone_notes], name
        assert catalog_entry.sounds_like is not None, name
        assert instruments.get(name) != instruments.get(catalog_entry.sounds_like), name


def test_a_cylindrical_chanter_sounds_odd_harmonics():
    """A cylindrical chanter's even harmonics are far below its odd ones; a conical one's are not.

    The chanter alone (its drones removed), at its middle note: a closed cylinder favours odd
    harmonics (Alban Faust, a maker, https://www.albanfaust.se/en/the-instrumentmaker/: "a
    single reed which sits on a cylindrically drilled chanter"), where every older bagpipe's
    chanter has every harmonic. Here the cylinder's second and fourth are under 0.05 of the
    first and the Highland pipe's second is above 0.6 (measured 0.815).
    """

    def relative_harmonics(name: str) -> list[float]:
        catalog_entry = instruments.entry(name)
        build = catalog_entry.build
        assert isinstance(build, partial), name
        chanter = build.func(**{**build.keywords, 'drones': ()})
        note = catalog_entry.middle_note()
        hertz = float(note.to_hz())
        samples = render_sound(spec_for(chanter, name=name, pitch=note.name, length=1.0)).samples
        held = samples[round(0.1 * SAMPLE_RATE) : round(0.9 * SAMPLE_RATE)]
        magnitude = np.abs(np.fft.rfft(held * np.hanning(len(held))))
        frequencies = np.fft.rfftfreq(len(held), 1 / SAMPLE_RATE)
        peaks = [
            float(np.max(magnitude[np.abs(frequencies - harmonic * hertz) < hertz / 4.0]))
            for harmonic in (1, 2, 3, 4)
        ]
        return [peak / peaks[0] for peak in peaks]

    cylinder = relative_harmonics('sackpipa')
    highland = relative_harmonics('highland bagpipe')
    assert cylinder[1] < 0.05
    assert cylinder[3] < 0.05
    assert highland[1] > 0.6


# Every name plans/data/instrument-audit/batch-13.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, a sourced
# footage or a sourced detune, and the alias rows that wait for one of them, in the sheet's order.
# None ships under that name or as an alias until the reason is met (decision 4; batch 13). The
# test matches exact names
ORGAN_HELD_BACK: dict[str, str] = {
    'diaphonic diapason': "its own build (the diaphone's beating pallet)",
    'gedeckt': 'a sourced footage',
    'kinura': 'its own build (inharmonic partials)',
    'larigot': 'a range above C8',
    'nasard': 'a range above C8',
    'organ bombarde': 'a sourced footage',
    'organ mixture': 'more than four sources',
    'organ trombone': 'a sourced footage',
    'piccolo organ': 'a range above C8',
    'rohrflote': 'a sourced footage',
    'scharff': 'more than four sources',
    'sesquialtera': 'a range above C8',
    'spitzflote': 'a sourced footage',
    'tierce': 'a range above C8',
    'vox humana': 'a pitch and amplitude LFO (the tremulant)',
    'bible regal': 'its own build (beating reeds in tiny pipes, not quite an inch long)',
}


def test_no_organ_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is an organ the sheet holds back."""
    assert set(ORGAN_HELD_BACK) & set(instruments.names()) == set()
    assert set(ORGAN_HELD_BACK) & set(instruments.ALIASES) == set()


def footage_feet(footage: str) -> float:
    """A footage as the sheet writes it ('16', '2 2/3') in feet.

    Returns:
        The footage in feet.
    """
    return float(sum(Fraction(part) for part in footage.split()))


def built_footage(catalog_entry: CatalogEntry) -> float:
    """The footage an organ entry sounds at: its own change, its parent's, or its build's keyword.

    Returns:
        The footage in feet (8.0 for an entry built at its keys' pitch).
    """
    if 'footage' in catalog_entry.sound_changes:
        return float(catalog_entry.sound_changes['footage'])
    if catalog_entry.sounds_like is not None:
        return built_footage(instruments.entry(catalog_entry.sounds_like))
    if isinstance(catalog_entry.build, partial):
        return float(catalog_entry.build.keywords.get('footage', 8.0))
    return 8.0


def test_blown_moves_its_tone_by_its_semitones():
    """A blown tone given semitones sounds that far from the note; none leaves it unchanged.

    An octave down repeats at twice the note's period, but so would the unmoved note (two of its
    periods), so the tone must also repeat better at the expected period than at half of it, as
    test_harmonic_instruments_sound_their_note checks: the unmoved A3 repeats equally well at
    both.
    """
    for semitones, expected_hertz in ((12.0, 440.0), (-12.0, 110.0)):
        instrument = blown(FLUTE_STOP_LEVELS, attack=0.04, release=0.15, semitones=semitones)
        samples = rendered(instrument, pitch='A3', name=f'blown {semitones}')
        held = samples[round(0.15 * SAMPLE_RATE) : round(0.35 * SAMPLE_RATE)]
        found = best_period_near(held, hertz=expected_hertz)
        assert abs(1200.0 * np.log2(found / expected_hertz)) < 30.0, (semitones, found)
        whole = repetition_at(held, period_seconds=1.0 / expected_hertz)
        half = repetition_at(held, period_seconds=0.5 / expected_hertz)
        assert whole > half + 0.05, (semitones, whole, half)
    assert blown(FLUTE_STOP_LEVELS, attack=0.04, release=0.15) == blown(
        FLUTE_STOP_LEVELS, attack=0.04, release=0.15, semitones=0.0
    )


def test_an_organ_stop_sounds_at_its_footage():
    """The organ entries not at 8' are exactly ORGAN_STOP_FOOTAGES, each at its footage.

    A sound-alike that changes anything changes only its footage, which the harmonic test measures.
    """
    organ_entries = instruments.entries(family=Family.ORGANS)
    off_unison = {
        catalog_entry.name: catalog_entry
        for catalog_entry in organ_entries
        if built_footage(catalog_entry) != 8.0
    }
    assert set(off_unison) == set(ORGAN_STOP_FOOTAGES)
    for name, footage in ORGAN_STOP_FOOTAGES.items():
        assert built_footage(off_unison[name]) == pytest.approx(footage_feet(footage)), name
    for catalog_entry in organ_entries:
        if catalog_entry.sound_changes:
            assert set(catalog_entry.sound_changes) == {'footage'}, catalog_entry.name


def test_the_mechanical_organs_are_tagged():
    """The self-playing organs, and only they, carry Tag.MECHANICAL."""
    assert instruments.names(family=Family.ORGANS, tag=Tag.MECHANICAL) == tuple(
        MECHANICAL_ORGAN_NAMES
    )


def eight_foot_relative_harmonics(name: str) -> list[float]:
    """An organ entry's harmonics 1 to 4 at 8', relative to the first, at its middle note.

    The entry's own build with ``footage`` set to 8.0, so a stop of another footage is measured
    at its keys, as test_a_cylindrical_chanter_sounds_odd_harmonics measures a chanter.

    Returns:
        The peaks at harmonics 1 to 4, each divided by the first.
    """
    catalog_entry = instruments.entry(name)
    build = catalog_entry.build
    assert isinstance(build, partial), name
    instrument = build.func(*build.args, **{**build.keywords, 'footage': 8.0})
    note = catalog_entry.middle_note()
    hertz = float(note.to_hz())
    samples = render_sound(spec_for(instrument, name=name, pitch=note.name, length=1.0)).samples
    held = samples[round(0.1 * SAMPLE_RATE) : round(0.9 * SAMPLE_RATE)]
    magnitude = np.abs(np.fft.rfft(held * np.hanning(len(held))))
    frequencies = np.fft.rfftfreq(len(held), 1 / SAMPLE_RATE)
    peaks = [
        float(np.max(magnitude[np.abs(frequencies - harmonic * hertz) < hertz / 4.0]))
        for harmonic in (1, 2, 3, 4)
    ]
    return [peak / peaks[0] for peak in peaks]


def test_a_stopped_or_closed_stop_sounds_odd_harmonics():
    """A stopped flue's and a closed reed's even harmonics are far below their odd ones.

    A stopped flue pipe gives no even harmonics (Audsley, The Organ of the Twentieth Century,
    https://archive.org/download/organoftwentieth00audsuoft/organoftwentieth00audsuoft_djvu.txt:
    "Covered pipes cannot give the uneven upper partial tones, such as the first or octave and
    the third or super-octave"), and the clarinet stop's half-length cylindrical resonators
    "reinforce the odd-numbered harmonics" (the Encyclopedia of Organ Stops,
    http://www.organstops.org/c/Clarinet.html). The stopped diapason (STOPPED_FLUTE_LEVELS) and
    the organ clarinet (CLOSED_REED_LEVELS) are set against the open stops they are made from,
    pipe organ flute and pipe organ reed, each at 8' at its middle note (F#4 for all four).
    Measured: the stopped diapason's second and fourth 0.00032 and the flute's second 0.100; the
    organ clarinet's second and fourth 0.00000 and the reed's second 0.750. The bounds (under
    0.01; above 0.05 and 0.5) keep room either side.
    """
    stopped_flute = eight_foot_relative_harmonics('stopped diapason')
    open_flute = eight_foot_relative_harmonics('pipe organ flute')
    closed_reed = eight_foot_relative_harmonics('organ clarinet')
    open_reed = eight_foot_relative_harmonics('pipe organ reed')
    assert stopped_flute[1] < 0.01
    assert stopped_flute[3] < 0.01
    assert open_flute[1] > 0.05
    assert closed_reed[1] < 0.01
    assert closed_reed[3] < 0.01
    assert open_reed[1] > 0.5


def test_a_compound_stop_sums_its_ranks_as_harmonics():
    """A compound stop's ranks sit at harmonics 8 / footage of the key, summed and normalised.

    The footage ruling's rule 4 (plans/2026-11-12-instrument-catalog-batch-13-implementation.md):
    an 8' and a 4' rank of (1.0, 0.5) sum to (1.0, 1.5, 0.0, 0.5), divided by its loudest 1.5;
    a 2 2/3' rank sounds the twelfth, harmonic 3, and a 1 3/5' rank the seventeenth, harmonic 5.
    A rank off the harmonic series, or above harmonic 32, is refused.
    """
    assert compound_stop_levels((1.0, 0.5), (8.0, 4.0)) == pytest.approx((
        1.0 / 1.5,
        1.0,
        0.0,
        0.5 / 1.5,
    ))
    assert compound_stop_levels((1.0,), (8.0 / 3.0,)) == (0.0, 0.0, 1.0)
    assert compound_stop_levels((1.0,), (1.6,)) == (0.0, 0.0, 0.0, 0.0, 1.0)
    with pytest.raises(ValueError, match='harmonic'):
        compound_stop_levels((1.0,), (3.0,))
    with pytest.raises(ValueError, match='32'):
        compound_stop_levels((1.0, 0.5), (0.25,))


def _sheet_number(node: ast.expr) -> float:
    """Read a footage the sheet writes as a number or a division of numbers (``8.0 / 3.0``).

    Only number literals and ``/`` are accepted, so nothing in the sheet is ever executed.

    Returns:
        The footage the node spells out.

    Raises:
        AssertionError: The sheet writes the footage some other way.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _sheet_number(node.left) / _sheet_number(node.right)
    message = f'the sheet writes a footage this test does not read: {ast.unparse(node)}'
    raise AssertionError(message)


def test_the_cornet_organ_ships_the_levels_its_sheet_row_names():
    """The cornet's own build matches the builder cell of its row in batch-13.tsv.

    The cell reads ``_pipe_stop(compound_stop_levels(FLUTE_STOP_LEVELS, (8.0, 4.0, 8.0 / 3.0,
    2.0, 1.6)), chiff=0.02)``. The footages are read out of the cell and run through
    compound_stop_levels, so the sheet and the shipped build can not drift apart.
    """
    sheet = Path(__file__).parents[2] / 'plans' / 'data' / 'instrument-audit' / 'batch-13.tsv'
    with sheet.open(encoding='utf-8', newline='') as sheet_file:
        rows = [
            row
            for row in csv.DictReader(sheet_file, delimiter='\t')
            if row['name'] == 'cornet organ'
        ]
    assert len(rows) == 1
    builder_cell = rows[0]['builder'].split(', as an inline partial')[0]
    builder_call = ast.parse(builder_cell, mode='eval').body
    assert isinstance(builder_call, ast.Call)
    compound_call = builder_call.args[0]
    assert isinstance(compound_call, ast.Call)
    footages_node = compound_call.args[1]
    assert isinstance(footages_node, ast.Tuple)
    footages = tuple(_sheet_number(element) for element in footages_node.elts)
    expected = compound_stop_levels(FLUTE_STOP_LEVELS, footages)

    build = instruments.entry('cornet organ').build
    assert isinstance(build, partial)
    assert build.args[0] == expected
    assert build.keywords == {'chiff': 0.02}
    assert all(level > 0.0 for level in expected[:5])
    assert max(expected) == 1.0


def test_compound_stop_levels_refuses_empty_levels_and_a_footage_of_zero():
    """Empty levels, no ranks and a footage of zero or less each raise a ValueError saying so."""
    with pytest.raises(ValueError, match='at least one harmonic level'):
        compound_stop_levels((), (8.0,))
    with pytest.raises(ValueError, match='at least one rank'):
        compound_stop_levels((1.0,), ())
    with pytest.raises(ValueError, match='above zero'):
        compound_stop_levels((1.0,), (0.0,))
    with pytest.raises(ValueError, match='above zero'):
        compound_stop_levels((1.0,), (-8.0,))


# Batch 14's double clarinets with a drone pipe, each with its drone notes as the sheet writes them
# (highest first), sounding at equal temperament under every note, in catalog order: the builds,
# then the sound-alikes that share one's drones (plans/data/instrument-audit/batch-14.tsv)
CLARINET_DRONES: dict[str, tuple[str, ...]] = {}
# Batch 14's double clarinets whose unison pipes are tuned apart, each with its sourced detune in
# cents, the chorus copy of _clarinet, in catalog order: the builds, then their sound-alikes
# (plans/data/instrument-audit/batch-14.tsv)
CLARINET_DETUNES: dict[str, float] = {}
# Every name plans/data/instrument-audit/batch-14.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, a sourced
# reed and bore, a sourced drone tuning or a sourced detune, and the alias rows that wait for one of
# them, in the sheet's order. None ships under that name or as an alias until the reason is met
# (decision 4; batch 14). The test matches exact names
CLARINET_HELD_BACK: dict[str, str] = {
    'contrabass birbyne': 'a sourced reed and bore',
    'tenor birbyne': 'a sourced reed and bore',
}


def test_no_clarinet_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a clarinet the sheet holds back."""
    assert set(CLARINET_HELD_BACK) & set(instruments.names()) == set()
    assert set(CLARINET_HELD_BACK) & set(instruments.ALIASES) == set()


def test_a_clarinet_sounds_its_sourced_drones():
    """A clarinet with a drone pipe sounds each drone at its sourced note, equal-tempered.

    The drones are the build's sources named ``drone_...``, at fixed hertz (A4 = 440 Hz, two
    decimals, as the catalog's builds write hertz), highest first. The clarinets with drones are
    exactly the ones the table lists, so a later task that ships one without listing it fails here.
    """
    with_drones = [
        catalog_entry.name
        for catalog_entry in instruments.entries(family=Family.CLARINETS)
        if any(
            source_name.startswith('drone_')
            for source_name, _source in instruments.get(catalog_entry.name).sources
        )
    ]
    assert with_drones == list(CLARINET_DRONES)
    for name, drone_notes in CLARINET_DRONES.items():
        drone_hertz = [
            float(source.pitch)
            for source_name, source in instruments.get(name).sources
            if source_name.startswith('drone_')
        ]
        assert drone_hertz == [round(float(Note(note).to_hz()), 2) for note in drone_notes], name
        assert name in NOT_PERIODIC_AT_THE_NOTE, name


def test_a_detuned_clarinet_beats_at_its_sourced_cents():
    """A clarinet with a chorus source beats at the detune its sheet row sources.

    The clarinets with a chorus source are exactly the ones the table lists.
    """
    with_chorus = [
        catalog_entry.name
        for catalog_entry in instruments.entries(family=Family.CLARINETS)
        if any(
            source_name == 'chorus'
            for source_name, _source in instruments.get(catalog_entry.name).sources
        )
    ]
    assert with_chorus == list(CLARINET_DETUNES)
    for name, cents in CLARINET_DETUNES.items():
        chorus_source = dict(instruments.get(name).sources)['chorus']
        assert chorus_source.detune_cents == pytest.approx(cents), name


# Batch 15's harpsichords that sound a 16' choir an octave below their keys (a sixteen_foot keyword
# on _harpsichord, added by the batch that first has a row needing it), in catalog order: the
# builds, then the sound-alikes that add one through sound_changes
# (plans/data/instrument-audit/batch-15.tsv)
KEYBOARD_SIXTEEN_FOOT_NAMES: list[str] = []
# Batch 15's keyboard idiophones built from their sourced partial ratios (a _keyed_idiophone
# builder, added by the batch that first has a row needing it), in catalog order: the builds, then
# their sound-alikes (plans/data/instrument-audit/batch-15.tsv)
KEYBOARD_PARTIAL_RATIOS: dict[str, tuple[float, ...]] = {}
# Every name plans/data/instrument-audit/batch-15.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, a sourced
# partial series, sub-audio fundamentals, a range above C8 or more than four sources, and the alias
# rows that wait for one of them, in the sheet's order. None ships under that name or as an alias
# until the reason is met (decision 4; batch 15). The test matches exact names
KEYBOARD_HELD_BACK: dict[str, str] = {}


def test_no_keyboard_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a keyboard the sheet holds back."""
    assert set(KEYBOARD_HELD_BACK) & set(instruments.names()) == set()
    assert set(KEYBOARD_HELD_BACK) & set(instruments.ALIASES) == set()


def test_the_mechanical_keyboards_are_tagged():
    """The self-playing keyboards, and only they, carry Tag.MECHANICAL."""
    assert instruments.names(family=Family.KEYBOARDS, tag=Tag.MECHANICAL) == tuple(
        MECHANICAL_KEYBOARD_NAMES
    )


def effective_keyboard_keywords(catalog_entry: CatalogEntry) -> dict[str, object]:
    """A keyboard entry's builder keywords: its parent's build, updated with its sound_changes.

    A plain-function build (``toy piano``'s) has no keywords.

    Returns:
        The keywords the entry's instrument is built with.
    """
    parent = instruments.entry(catalog_entry.sounds_like or catalog_entry.name)
    keywords = dict(getattr(parent.build, 'keywords', {}))
    keywords.update(catalog_entry.sound_changes)
    return keywords


def has_octave_down_source(name: str) -> bool:
    """Whether the entry's instrument has a source sounding an octave (-12 semitones) below.

    Returns:
        True when one of the instrument's sources is offset by -12.0 semitones.
    """
    semitones = [float(source.semitones) for _name, source in instruments.get(name).sources]
    return -12.0 in semitones


def test_the_octave_down_source_check_tells_builds_apart():
    """The 16' guard's check finds bourdon's octave-down source and none on toy piano."""
    assert has_octave_down_source('bourdon')
    assert not has_octave_down_source('toy piano')


def test_a_sixteen_foot_harpsichord_sounds_its_lower_choir():
    """The harpsichords with a 16' choir are the ones the table lists, each sounding it."""
    with_sixteen_foot = [
        catalog_entry.name
        for catalog_entry in instruments.entries(family=Family.KEYBOARDS)
        if effective_keyboard_keywords(catalog_entry).get('sixteen_foot') is True
    ]
    assert with_sixteen_foot == KEYBOARD_SIXTEEN_FOOT_NAMES
    for name in KEYBOARD_SIXTEEN_FOOT_NAMES:
        assert has_octave_down_source(name), name


def attack_peak_offsets(name: str, ratios: tuple[float, ...]) -> tuple[list[float], float]:
    """How far the entry's attack spectrum's nearest peak is from each ratio's frequency.

    The attack (0.005 to 0.155 s), where the upper partials, which ring shorter than the
    fundamental, are still strong: a window over the held note would find only the fundamental.
    The peaks are the local maxima above 2% of the strongest.

    Returns:
        Each ratio's offset in hertz from the nearest peak, and the tolerance: the tighter of a
        tenth of the fundamental (so 2.76 is not 3.0) and four FFT bins.
    """
    note = instruments.entry(name).middle_note()
    hertz = float(note.to_hz())
    samples = render_sound(
        spec_for(instruments.get(name), name=name, pitch=note.name, length=1.0)
    ).samples
    attack = samples[round(0.005 * SAMPLE_RATE) : round(0.155 * SAMPLE_RATE)]
    magnitude = np.abs(np.fft.rfft(attack * np.hanning(len(attack))))
    frequencies = np.fft.rfftfreq(len(attack), 1 / SAMPLE_RATE)
    is_peak = (
        (magnitude[1:-1] > magnitude[:-2])
        & (magnitude[1:-1] >= magnitude[2:])
        & (magnitude[1:-1] > 0.02 * np.max(magnitude))
    )
    peak_frequencies = frequencies[1:-1][is_peak]
    offsets = [float(np.min(np.abs(peak_frequencies - ratio * hertz))) for ratio in ratios]
    return offsets, min(hertz / 10.0, 4.0 * SAMPLE_RATE / len(attack))


def test_the_attack_window_finds_the_toy_pianos_own_partials_and_no_others():
    """Toy piano's own ratios are each within tolerance of a peak; 3.0 for 2.76 is not."""
    own_ratios = (1.0, 2.76, 5.40)
    offsets, tolerance = attack_peak_offsets('toy piano', own_ratios)
    for ratio, offset in zip(own_ratios, offsets, strict=True):
        assert offset <= tolerance, (ratio, offset, tolerance)

    wrong_ratios = (1.0, 3.0, 5.40)
    offsets, tolerance = attack_peak_offsets('toy piano', wrong_ratios)
    assert offsets[0] <= tolerance
    assert offsets[1] > tolerance
    assert offsets[2] <= tolerance


def test_a_keyed_idiophone_sounds_its_sourced_partials():
    """The keyboards with sourced partial ratios are the table's, each sounding them."""
    with_ratios = {
        catalog_entry.name: effective_keyboard_keywords(catalog_entry)['ratios']
        for catalog_entry in instruments.entries(family=Family.KEYBOARDS)
        if 'ratios' in effective_keyboard_keywords(catalog_entry)
    }
    assert list(with_ratios) == list(KEYBOARD_PARTIAL_RATIOS)
    for name, ratios in KEYBOARD_PARTIAL_RATIOS.items():
        assert with_ratios[name] == ratios, name
        offsets, tolerance = attack_peak_offsets(name, ratios)
        for ratio, offset in zip(ratios, offsets, strict=True):
            assert offset <= tolerance, (name, ratio, offset, tolerance)


# Batch 16's free reeds with fixed drones, each with its drone notes as the sheet writes them
# (highest first), sounding at equal temperament under every note, in catalog order: the builds,
# then their sound-alikes (plans/data/instrument-audit/batch-16.tsv). No free reed builder takes
# drones yet, so the table stays empty until one is added
FREE_REED_DRONES: dict[str, tuple[str, ...]] = {}
# Batch 16's free reed sound-alikes whose sourced detune between reed sets differs from their
# parent's, each with its cents (sound_changes={'cents': ...} once a builder takes cents), in the
# sheet's order
# (plans/data/instrument-audit/batch-16.tsv)
FREE_REED_DETUNES: dict[str, float] = {}
# Batch 16's free reed sound-alikes with a sourced reed set an octave above the unison
# (sound_changes={'footages': (8.0, 4.0)} once a builder takes footages), in the sheet's order
# (plans/data/instrument-audit/batch-16.tsv)
FREE_REED_REED_SETS: dict[str, tuple[float, ...]] = {}
# Every name plans/data/instrument-audit/batch-16.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, a sourced
# drone tuning or detune, sub-audio fundamentals, a range above C8 or more than four sources, and
# the alias rows that wait for one of them, in the sheet's order. None ships under that name or as
# an alias until the reason is met (decision 4; batch 16). The test matches exact names
FREE_REED_HELD_BACK: dict[str, str] = {}


def names_listed(names: Iterable[str]) -> set[str]:
    """The given names that are catalog names or aliases.

    Returns:
        The names the catalog lists, under their own name or as an alias.
    """
    return set(names) & (set(instruments.names()) | set(instruments.ALIASES))


def drone_hertz(name: str) -> list[float]:
    """The hertz of each drone source in the entry's instrument, in build order.

    Returns:
        The fixed pitch of every source named ``drone_...``.
    """
    return [
        float(source.pitch)
        for source_name, source in instruments.get(name).sources
        if source_name.startswith('drone_')
    ]


def chorus_detune_cents(name: str) -> float | None:
    """The detune of the entry's chorus source, the second reed set beating against the first.

    Returns:
        The chorus source's ``detune_cents``, or None when the instrument has no chorus source.
    """
    chorus_source = dict(instruments.get(name).sources).get('chorus')
    return None if chorus_source is None else float(chorus_source.detune_cents)


def effective_free_reed_keywords(catalog_entry: CatalogEntry) -> dict[str, object]:
    """A free reed entry's builder keywords: its parent's build, updated with its sound_changes.

    Returns:
        The keywords the entry's instrument is built with.
    """
    parent = instruments.entry(catalog_entry.sounds_like or catalog_entry.name)
    keywords = dict(getattr(parent.build, 'keywords', {}))
    keywords.update(catalog_entry.sound_changes)
    return keywords


def tone_wave(name: str) -> Wave:
    """The wave of the entry's tone source, its harmonic series.

    Returns:
        The ``tone`` source's content.
    """
    content = dict(instruments.get(name).sources)['tone'].content
    assert isinstance(content, Wave)
    return content


def test_the_free_reed_guards_helpers_read_real_builds():
    """Each free reed guard's helper reads a real catalog build, as batch 15's review required."""
    assert names_listed(['harmonica', 'fender rhodes', 'not an instrument']) == {
        'harmonica',
        'fender rhodes',
    }
    assert drone_hertz('highland bagpipe') == [240.0, 120.0]
    assert drone_hertz('harmonica') == []
    assert chorus_detune_cents('musette accordion') == 15.0
    assert chorus_detune_cents('harmonica') is None
    assert effective_free_reed_keywords(instruments.entry('musette accordion')) == {
        'cents': 15.0,
        'low_pass': 6000.0,
    }
    assert tone_wave('harmonica') == wave_from_levels(FREE_REED_LEVELS)


def synthetic_free_reed_sound_alike() -> CatalogEntry:
    """A free reed sound-alike built here, since no sheet row ships one.

    It sounds like the musette accordion (a parent with its own ``cents`` and ``low_pass``) and
    changes only the ``cents``.

    Returns:
        The entry, which is in no catalog.
    """
    return CatalogEntry(
        'test free reed sound alike',
        'Test free reed sound-alike',
        Family.FREE_REEDS,
        'C3',
        'C6',
        sounds_like='musette accordion',
        sound_changes={'cents': 9.0},
    )


def test_a_sound_alikes_keywords_start_from_its_parents_build_and_take_its_sound_changes():
    """The helper starts from the parent's build keywords, which the entry's own lack.

    Its ``sound_changes`` replace the parent's value and leave the parent's other keywords.
    """
    keywords = effective_free_reed_keywords(synthetic_free_reed_sound_alike())
    assert keywords == {'cents': 9.0, 'low_pass': 6000.0}


def test_no_free_reed_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a free reed the sheet holds back."""
    assert names_listed(FREE_REED_HELD_BACK) == set()


def test_the_mechanical_free_reeds_are_tagged():
    """The self-playing free reeds, and only they, carry Tag.MECHANICAL."""
    assert instruments.names(family=Family.FREE_REEDS, tag=Tag.MECHANICAL) == tuple(
        MECHANICAL_FREE_REED_NAMES
    )


def test_a_droned_free_reed_sounds_its_sourced_drones():
    """A free reed with drones sounds each at its sourced note, equal-tempered.

    The free reeds with drones are exactly the ones the table lists, so a later task that ships
    one without listing it fails here.
    """
    with_drones = [
        catalog_entry.name
        for catalog_entry in instruments.entries(family=Family.FREE_REEDS)
        if drone_hertz(catalog_entry.name)
    ]
    assert with_drones == list(FREE_REED_DRONES)
    for name, drone_notes in FREE_REED_DRONES.items():
        assert drone_hertz(name) == [round(float(Note(note).to_hz()), 2) for note in drone_notes], (
            name
        )
        assert name in NOT_PERIODIC_AT_THE_NOTE, name


def test_a_detuned_free_reed_beats_at_its_sourced_cents():
    """A free reed sound-alike with a sourced detune beats at it.

    The free reeds whose sound_changes hold cents are exactly the ones the table lists.
    """
    with_detune = [
        catalog_entry.name
        for catalog_entry in instruments.entries(family=Family.FREE_REEDS)
        if 'cents' in catalog_entry.sound_changes
    ]
    assert with_detune == list(FREE_REED_DETUNES)
    for name, cents in FREE_REED_DETUNES.items():
        assert chorus_detune_cents(name) == pytest.approx(cents), name


def test_a_free_reed_reed_set_sounds_its_octave():
    """A free reed with a reed set an octave above its unison sounds the compound series.

    The free reeds whose keywords hold footages other than (8.0,) are exactly the table's.
    """
    with_reed_set = [
        catalog_entry.name
        for catalog_entry in instruments.entries(family=Family.FREE_REEDS)
        if effective_free_reed_keywords(catalog_entry).get('footages', (8.0,)) != (8.0,)
    ]
    assert with_reed_set == list(FREE_REED_REED_SETS)
    for name, footages in FREE_REED_REED_SETS.items():
        assert tone_wave(name) == wave_from_levels(
            compound_stop_levels(FREE_REED_LEVELS[:16], footages)
        ), name


# Every name plans/data/instrument-audit/batch-17.tsv holds back for any reason but a sourced
# range, with its waits_for: the WAIT rows for an engine feature, a build of its own, sub-audio
# fundamentals or a range above C8, and the alias rows that wait for one of them, in the sheet's
# order. None ships under that name or as an alias until the reason is met (decision 4; batch
# 17). The test matches exact names
HARP_HELD_BACK: dict[str, str] = {}


def entries_with_sound_changes(family: Family) -> list[str]:
    """The names of the family's entries whose sound_changes are not empty.

    Returns:
        The names, in catalog order.
    """
    return [
        catalog_entry.name
        for catalog_entry in instruments.entries(family=family)
        if catalog_entry.sound_changes
    ]


def test_the_harp_guards_helpers_read_real_builds():
    """Each harp guard's helper reads a real catalog build, as batch 15's review required."""
    assert names_listed(['concert harp', 'fender rhodes', 'not an instrument']) == {
        'concert harp',
        'fender rhodes',
    }
    assert entries_with_sound_changes(Family.ORGANS) == ['bourdon']
    assert entries_with_sound_changes(Family.HARPS) == []


def test_no_harp_name_held_back_for_a_feature_is_listed():
    """No catalog name or alias is a harp the sheet holds back."""
    assert names_listed(HARP_HELD_BACK) == set()


def test_no_harp_sound_alike_changes_its_parents_build():
    """No harp sound-alike carries sound_changes: this batch adds none, as the sheet rules."""
    assert entries_with_sound_changes(Family.HARPS) == []
