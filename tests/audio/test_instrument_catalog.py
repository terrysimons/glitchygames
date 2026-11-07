"""The instrument catalog: every entry builds, renders across its range and plays its pitch."""

import numpy as np
import pytest

from glitchygames.audio import instruments
from glitchygames.audio.instrument import Filter, Instrument
from glitchygames.audio.instruments import CatalogEntry, Family, Tag
from glitchygames.audio.instruments.registry import FAMILY_TABLES, aliases_from, catalog_from
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
    for entry in instruments.entries(family=Family.ORGANS)
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
        if entry.family in HARMONIC_FAMILIES and entry.name not in NOT_PERIODIC_AT_THE_NOTE
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
    for organ in instruments.entries(family=Family.ORGANS):
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
    assert instruments.names(tag=Tag.MECHANICAL) == ('music box',)


def test_the_sansula_rings_longer_and_brighter_than_the_kalimba():
    """The sansula ships as its own entry because it sounds different from the kalimba."""
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
    [('zanza', 'mbira'), ('cylinder music box', 'music box'), ('disc music box', 'music box')],
)
def test_the_plucked_idiophone_aliases_resolve(alias, target):
    """Zanza is the mbira; both music-box mechanisms play the one comb."""
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
