"""Plucked strings: guitars, basses, lutes and their kin.

Ranges are sounding pitch (a guitar sounds an octave below written), after the common tunings
of fretted and folk instruments. Timbres: a plucked string lacks the harmonics with a node where
it is plucked (``plucked_series``) and rings down, low strings longer; paired courses beat; a
sitar's or tanpura's bridge (jawari) adds buzz.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.plucked_sound_alikes import PLUCKED_SOUND_ALIKES
from glitchygames.audio.instruments.timbres import Course, plucked, plucked_series

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument


def _plucked(  # ruff: ignore[too-many-arguments] - the plucked family's traits
    *,
    ring_seconds: float,
    low_pass: float,
    slope: float = 6.0,
    position: float = 0.2,
    courses: tuple[Course, ...] = (),
    pick: float = 0.0,
    sustain: float = 0.0,
    drive: float = 0.0,
    attack: float = 0.002,
) -> Instrument:
    return plucked(
        plucked_series(count=28, decibels_per_octave=slope, pluck_position=position),
        ring_seconds=ring_seconds,
        release=min(0.6, ring_seconds / 2.0),
        attack=attack,
        sustain=sustain,
        courses=courses,
        pick=pick,
        low_pass=low_pass,
        drive=drive,
    )


PAIRED: Final[tuple[Course, ...]] = (Course(cents=3.0),)
OCTAVE_PAIRED: Final[tuple[Course, ...]] = (Course(semitones=12.0, cents=2.0, level=0.55),)
# An instrument's courses apply to every note it plays: a twelve-string guitar's octave pairs
# (only the four lower courses; its B and E courses are unison) and a bouzouki's (the lower one
# or two courses) are approximated by doubling every note, so their high notes sound fuller than
# the real instrument's
SYMPATHETIC: Final[tuple[Course, ...]] = (
    Course(cents=4.0, level=0.5),
    Course(semitones=12.0, cents=-3.0, level=0.3),
)

NYLON_GUITAR = partial(_plucked, ring_seconds=2.5, low_pass=4000.0, slope=7.0, position=0.18)
STEEL_GUITAR = partial(
    _plucked, ring_seconds=3.0, low_pass=6500.0, slope=5.0, position=0.15, pick=0.05
)
ELECTRIC_BASS = partial(_plucked, ring_seconds=2.5, low_pass=1800.0, slope=7.5, position=0.25)
LUTE = partial(
    _plucked, ring_seconds=1.8, low_pass=4500.0, slope=6.5, position=0.15, courses=PAIRED
)
BRIGHT_LUTE = partial(
    _plucked, ring_seconds=1.2, low_pass=7000.0, slope=4.0, position=0.1, courses=PAIRED, pick=0.05
)
BUZZING_LUTE = partial(
    _plucked,
    ring_seconds=2.5,
    low_pass=7000.0,
    slope=2.5,
    position=0.12,
    courses=SYMPATHETIC,
    drive=1.0,
)
SHORT_LUTE = partial(
    _plucked, ring_seconds=0.9, low_pass=6000.0, slope=4.5, position=0.12, pick=0.06
)

_PLUCKED_BUILDS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'classical guitar',
        'Classical guitar (nylon)',
        Family.PLUCKED_STRINGS,
        'E2',
        'B5',
        NYLON_GUITAR,
    ),
    CatalogEntry(
        'acoustic guitar',
        'Acoustic guitar (steel)',
        Family.PLUCKED_STRINGS,
        'E2',
        'C6',
        STEEL_GUITAR,
    ),
    CatalogEntry(
        'twelve string guitar',
        'Twelve-string guitar',
        Family.PLUCKED_STRINGS,
        'E2',
        'C6',
        partial(
            _plucked,
            ring_seconds=3.0,
            low_pass=7000.0,
            slope=5.0,
            position=0.15,
            courses=OCTAVE_PAIRED,
            pick=0.05,
        ),
    ),
    CatalogEntry(
        'baritone guitar',
        'Baritone guitar',
        Family.PLUCKED_STRINGS,
        'B1',
        'E5',
        partial(_plucked, ring_seconds=3.0, low_pass=5000.0, slope=5.5, position=0.15, pick=0.04),
    ),
    CatalogEntry(
        'resonator guitar',
        'Resonator guitar (dobro)',
        Family.PLUCKED_STRINGS,
        'G2',
        'D6',
        partial(
            _plucked,
            ring_seconds=2.5,
            low_pass=6000.0,
            slope=3.5,
            position=0.1,
            pick=0.05,
            drive=0.6,
        ),
    ),
    CatalogEntry(
        'jazz guitar',
        'Jazz guitar (archtop)',
        Family.PLUCKED_STRINGS,
        'E2',
        'D6',
        partial(_plucked, ring_seconds=2.0, low_pass=2200.0, slope=7.0, position=0.25),
    ),
    CatalogEntry(
        'electric guitar',
        'Electric guitar (clean)',
        Family.PLUCKED_STRINGS,
        'E2',
        'E6',
        partial(_plucked, ring_seconds=4.0, low_pass=5000.0, slope=5.5, position=0.22, pick=0.03),
    ),
    CatalogEntry(
        'electric guitar overdrive',
        'Electric guitar (overdrive)',
        Family.PLUCKED_STRINGS,
        'E2',
        'E6',
        partial(
            _plucked,
            ring_seconds=3.0,
            low_pass=3800.0,
            slope=5.5,
            position=0.22,
            sustain=0.3,
            drive=4.0,
        ),
    ),
    CatalogEntry(
        'electric guitar distortion',
        'Electric guitar (distortion)',
        Family.PLUCKED_STRINGS,
        'E2',
        'E6',
        partial(
            _plucked,
            ring_seconds=3.0,
            low_pass=3200.0,
            slope=5.5,
            position=0.22,
            sustain=0.55,
            drive=12.0,
        ),
    ),
    CatalogEntry(
        'lap steel guitar',
        'Lap steel guitar',
        Family.PLUCKED_STRINGS,
        'G2',
        'E6',
        partial(
            _plucked,
            ring_seconds=5.0,
            low_pass=4500.0,
            slope=6.0,
            position=0.2,
            sustain=0.15,
            attack=0.015,
        ),
    ),
    CatalogEntry(
        'pedal steel guitar',
        'Pedal steel guitar',
        Family.PLUCKED_STRINGS,
        'B2',
        'G6',
        partial(
            _plucked,
            ring_seconds=6.0,
            low_pass=5000.0,
            slope=6.0,
            position=0.2,
            sustain=0.2,
            attack=0.03,
        ),
    ),
    CatalogEntry(
        'bass guitar', 'Electric bass (fingered)', Family.PLUCKED_STRINGS, 'E1', 'G4', ELECTRIC_BASS
    ),
    CatalogEntry(
        'picked bass',
        'Electric bass (picked)',
        Family.PLUCKED_STRINGS,
        'E1',
        'G4',
        partial(_plucked, ring_seconds=2.0, low_pass=3200.0, slope=5.0, position=0.12, pick=0.06),
    ),
    CatalogEntry(
        'slap bass',
        'Electric bass (slap)',
        Family.PLUCKED_STRINGS,
        'E1',
        'G4',
        partial(_plucked, ring_seconds=1.2, low_pass=6000.0, slope=3.5, position=0.08, pick=0.12),
    ),
    CatalogEntry(
        'fretless bass',
        'Fretless bass',
        Family.PLUCKED_STRINGS,
        'E1',
        'G4',
        partial(
            _plucked,
            ring_seconds=3.0,
            low_pass=2200.0,
            slope=7.0,
            position=0.3,
            sustain=0.15,
            attack=0.012,
        ),
    ),
    CatalogEntry(
        'five string bass', 'Five-string bass', Family.PLUCKED_STRINGS, 'B0', 'G4', ELECTRIC_BASS
    ),
    CatalogEntry(
        'six string bass', 'Six-string bass', Family.PLUCKED_STRINGS, 'B0', 'C5', ELECTRIC_BASS
    ),
    CatalogEntry(
        'acoustic bass guitar',
        'Acoustic bass guitar',
        Family.PLUCKED_STRINGS,
        'E1',
        'G4',
        partial(_plucked, ring_seconds=1.8, low_pass=2000.0, slope=7.0, position=0.2, pick=0.02),
    ),
    CatalogEntry(
        'soprano ukulele',
        'Soprano ukulele',
        Family.PLUCKED_STRINGS,
        'C4',
        'A5',
        partial(_plucked, ring_seconds=0.9, low_pass=5000.0, slope=6.5, position=0.2),
    ),
    CatalogEntry(
        'concert ukulele',
        'Concert ukulele',
        Family.PLUCKED_STRINGS,
        'C4',
        'C6',
        partial(_plucked, ring_seconds=1.0, low_pass=5000.0, slope=6.5, position=0.2),
    ),
    CatalogEntry(
        'tenor ukulele',
        'Tenor ukulele',
        Family.PLUCKED_STRINGS,
        'C4',
        'C6',
        partial(_plucked, ring_seconds=1.2, low_pass=4800.0, slope=6.5, position=0.2),
    ),
    CatalogEntry(
        'baritone ukulele',
        'Baritone ukulele',
        Family.PLUCKED_STRINGS,
        'D3',
        'E5',
        partial(_plucked, ring_seconds=1.4, low_pass=4500.0, slope=6.5, position=0.2),
    ),
    CatalogEntry(
        'banjo',
        'Five-string banjo',
        Family.PLUCKED_STRINGS,
        'D3',
        'D6',
        partial(_plucked, ring_seconds=0.9, low_pass=8000.0, slope=2.5, position=0.08, pick=0.1),
    ),
    CatalogEntry(
        'tenor banjo',
        'Tenor banjo',
        Family.PLUCKED_STRINGS,
        'C3',
        'A5',
        partial(_plucked, ring_seconds=0.9, low_pass=7500.0, slope=2.5, position=0.08, pick=0.1),
    ),
    CatalogEntry('mandolin', 'Mandolin', Family.PLUCKED_STRINGS, 'G3', 'B6', BRIGHT_LUTE),
    CatalogEntry('mandola', 'Mandola', Family.PLUCKED_STRINGS, 'C3', 'E6', BRIGHT_LUTE),
    CatalogEntry('octave mandolin', 'Octave mandolin', Family.PLUCKED_STRINGS, 'G2', 'B5', LUTE),
    CatalogEntry('mandocello', 'Mandocello', Family.PLUCKED_STRINGS, 'C2', 'A5', LUTE),
    CatalogEntry(
        'irish bouzouki',
        'Irish bouzouki',
        Family.PLUCKED_STRINGS,
        'G2',
        'A5',
        partial(
            _plucked,
            ring_seconds=2.0,
            low_pass=6000.0,
            slope=5.0,
            position=0.12,
            courses=OCTAVE_PAIRED,
            pick=0.05,
        ),
    ),
    CatalogEntry(
        'greek bouzouki', 'Greek bouzouki', Family.PLUCKED_STRINGS, 'C3', 'D6', BRIGHT_LUTE
    ),
    CatalogEntry('lute', 'Renaissance lute', Family.PLUCKED_STRINGS, 'G2', 'C6', LUTE),
    CatalogEntry('archlute', 'Archlute', Family.PLUCKED_STRINGS, 'G1', 'C6', LUTE),
    CatalogEntry('theorbo', 'Theorbo', Family.PLUCKED_STRINGS, 'A1', 'A5', LUTE),
    CatalogEntry('baroque guitar', 'Baroque guitar', Family.PLUCKED_STRINGS, 'D3', 'C6', LUTE),
    CatalogEntry('vihuela', 'Vihuela', Family.PLUCKED_STRINGS, 'G2', 'C6', LUTE),
    CatalogEntry('cittern', 'Cittern', Family.PLUCKED_STRINGS, 'G3', 'D6', BRIGHT_LUTE),
    CatalogEntry(
        'oud',
        'Oud',
        Family.PLUCKED_STRINGS,
        'C2',
        'G5',
        partial(
            _plucked,
            ring_seconds=1.6,
            low_pass=4500.0,
            slope=5.5,
            position=0.12,
            courses=PAIRED,
            pick=0.06,
        ),
    ),
    CatalogEntry('saz', 'Saz (bağlama)', Family.PLUCKED_STRINGS, 'A2', 'A5', BRIGHT_LUTE),
    CatalogEntry('sitar', 'Sitar', Family.PLUCKED_STRINGS, 'C3', 'C6', BUZZING_LUTE),
    CatalogEntry('tanpura', 'Tanpura', Family.PLUCKED_STRINGS, 'C2', 'C4', BUZZING_LUTE),
    CatalogEntry('veena', 'Saraswati veena', Family.PLUCKED_STRINGS, 'G2', 'C6', BUZZING_LUTE),
    CatalogEntry(
        'sarod',
        'Sarod',
        Family.PLUCKED_STRINGS,
        'C3',
        'C6',
        partial(
            _plucked,
            ring_seconds=1.8,
            low_pass=6000.0,
            slope=4.0,
            position=0.1,
            courses=SYMPATHETIC,
            pick=0.05,
        ),
    ),
    CatalogEntry(
        'koto',
        'Koto',
        Family.PLUCKED_STRINGS,
        'D3',
        'D6',
        partial(_plucked, ring_seconds=1.8, low_pass=6000.0, slope=4.5, position=0.1, pick=0.05),
    ),
    CatalogEntry(
        'shamisen',
        'Shamisen',
        Family.PLUCKED_STRINGS,
        'C3',
        'C6',
        partial(
            _plucked,
            ring_seconds=0.7,
            low_pass=7000.0,
            slope=3.0,
            position=0.08,
            pick=0.12,
            drive=0.6,
        ),
    ),
    CatalogEntry('pipa', 'Pipa', Family.PLUCKED_STRINGS, 'A2', 'D6', SHORT_LUTE),
    CatalogEntry(
        'guzheng',
        'Guzheng',
        Family.PLUCKED_STRINGS,
        'D2',
        'D6',
        partial(_plucked, ring_seconds=2.5, low_pass=6000.0, slope=4.5, position=0.12, pick=0.04),
    ),
    CatalogEntry(
        'gayageum',
        'Gayageum',
        Family.PLUCKED_STRINGS,
        'Eb2',
        'Eb5',
        partial(_plucked, ring_seconds=1.6, low_pass=4000.0, slope=6.0, position=0.2),
    ),
    CatalogEntry('balalaika', 'Prima balalaika', Family.PLUCKED_STRINGS, 'E4', 'E6', SHORT_LUTE),
    CatalogEntry(
        'bass balalaika',
        'Bass balalaika',
        Family.PLUCKED_STRINGS,
        'E1',
        'E4',
        partial(_plucked, ring_seconds=1.5, low_pass=2500.0, slope=6.0, position=0.15, pick=0.04),
    ),
    CatalogEntry('domra', 'Domra', Family.PLUCKED_STRINGS, 'E4', 'E6', SHORT_LUTE),
    CatalogEntry('charango', 'Charango', Family.PLUCKED_STRINGS, 'E4', 'E6', BRIGHT_LUTE),
    CatalogEntry('cuatro', 'Venezuelan cuatro', Family.PLUCKED_STRINGS, 'A3', 'A5', SHORT_LUTE),
    CatalogEntry('tres', 'Cuban tres', Family.PLUCKED_STRINGS, 'G3', 'C6', BRIGHT_LUTE),
    CatalogEntry(
        'appalachian dulcimer',
        'Appalachian dulcimer',
        Family.PLUCKED_STRINGS,
        'D3',
        'D6',
        partial(
            _plucked,
            ring_seconds=2.0,
            low_pass=5500.0,
            slope=5.0,
            position=0.12,
            courses=PAIRED,
            pick=0.04,
        ),
    ),
    CatalogEntry(
        'zither',
        'Concert zither',
        Family.PLUCKED_STRINGS,
        'C2',
        'C6',
        partial(_plucked, ring_seconds=2.5, low_pass=6000.0, slope=4.5, position=0.1, pick=0.04),
    ),
    CatalogEntry(
        'autoharp',
        'Autoharp',
        Family.PLUCKED_STRINGS,
        'F2',
        'C6',
        partial(_plucked, ring_seconds=2.5, low_pass=5500.0, slope=5.0, position=0.12, pick=0.05),
    ),
    CatalogEntry(
        'kantele',
        'Kantele',
        Family.PLUCKED_STRINGS,
        'D4',
        'D5',
        partial(_plucked, ring_seconds=2.5, low_pass=5000.0, slope=5.0, position=0.15),
    ),
    CatalogEntry(
        'psaltery',
        'Psaltery',
        Family.PLUCKED_STRINGS,
        'C4',
        'C6',
        partial(_plucked, ring_seconds=2.0, low_pass=6500.0, slope=4.0, position=0.1, pick=0.04),
    ),
    # --- Batch 4's necked lutes with their own build, in the order of
    # plans/data/instrument-audit/batch-4.tsv; the sound-alikes that share these builds are in
    # ``plucked_sound_alikes.py``. Each build's numbers are sound design unless a comment says a
    # source gives them
    # Sound and range: https://en.wikipedia.org/wiki/Ang%C3%A9lique_(instrument) ("A two-headed
    # lute, it contains ten single strings on the lower head and six or seven single strings on
    # the upper head"; "Differing from the lute, the 16 or 17 string angelica was single-strung
    # like a theorbo"; "produced a full and clear tone by the increased use of open strings";
    # sounded with bare hands and fingers; range "C - E - F - G - A - B - c - d - e - f - g - a
    # - b - c' - d' - e'", Helmholtz C = C2, e' = E4, the open-string compass). The lute's
    # traits without its courses, single-strung and fingered: the numbers are the catalog's LUTE
    # values (sound design)
    CatalogEntry(
        'angelique',
        'Angélique (angel lute)',
        Family.PLUCKED_STRINGS,
        'C2',
        'E4',
        partial(_plucked, ring_seconds=1.8, low_pass=4500.0, slope=6.5, position=0.15),
    ),
    # Sound and range: https://en.wikipedia.org/wiki/Banjolele ("a four-stringed musical
    # instrument with a small banjo-type body and a fretted ukulele neck"; "Banjo ukulele heads
    # were traditionally made of calf skin, but most modern instruments are fitted with
    # synthetic heads"; "The head typically has a firm tension"; "originally outfitted with gut
    # strings. Nylon strings are now typically used"; "The banjo ukulele neck typically has
    # sixteen frets"; "commonly tuned G4 C4 E4 A4", with a re-entrant 4th string). Range derived
    # from the page: lowest C4 (the re-entrant G4 is above it), highest A4 + 16 frets = C#6. A
    # skin head's short, bright ring on gut or nylon strings (softer than the banjo's steel); no
    # source gives a plectrum, so no pick click. Every number is sound design
    CatalogEntry(
        'banjolele',
        'Banjo ukulele (banjolele)',
        Family.PLUCKED_STRINGS,
        'C4',
        'C#6',
        partial(_plucked, ring_seconds=0.8, low_pass=6000.0, slope=4.0, position=0.12),
    ),
    # Sound and range: https://en.wikipedia.org/wiki/Chapman_Stick ("While the electric guitar
    # is usually played by strumming or plucking the strings, the Chapman stick is usually
    # played by tapping or fretting the strings"; "a long scale length, stainless steel
    # pyramidal fret rails, very low string action, and very sensitive pickups"; "The 36\"
    # scale-length standard-sized Chapman Stick in Matched Reciprocal tuning can play from
    # C1-C6"). Tapped, not plucked: no pick click, a rounder attack, the position further from
    # the bridge, and the long ring of a long-scale electric instrument. Every number is sound
    # design
    CatalogEntry(
        'chapman stick',
        'Chapman Stick',
        Family.PLUCKED_STRINGS,
        'C1',
        'C6',
        partial(_plucked, ring_seconds=4.0, low_pass=4500.0, slope=6.5, position=0.3, attack=0.004),
    ),
    # Sound: https://en.wikipedia.org/wiki/Ruan_(instrument) ("It is a lute with a fretted neck,
    # a circular body, and four strings"; strings "made of steel (flatwound for the lower
    # strings)"; "Mainstream ruan players use plectrums"; "The instrument produces a mellow
    # tone"). Range from the same page, the tenor size (zhongruan, "tuning: G2-D3-G3-D4", "24
    # frets with 12 semitones on each string"): lowest G2, highest D4 + 24 frets = D6. A mellow
    # plectrum-played steel lute; every number is sound design
    CatalogEntry(
        'ruan',
        'Ruan (zhongruan)',
        Family.PLUCKED_STRINGS,
        'G2',
        'D6',
        partial(_plucked, ring_seconds=1.8, low_pass=3500.0, slope=6.0, position=0.15, pick=0.05),
    ),
    # Sound: https://en.wikipedia.org/wiki/Tar_(lute) ("a thin membrane covering the top"; "The
    # Persian tar has three double courses of strings"; "each pair tuned in unison"; "plucked at
    # the centre of the body using a small brass plectrum"). Range:
    # https://www.geidai.ac.jp/labs/koizumi/gcato/english/html-text/268.html ("body: mulberry
    # wood, with sheep foetus skin over front face"; "frets: 23, gut, movable"; "range: ca.
    # c-g\"", C3 to G5, approximate). A skin belly's short, bright ring (as the banjo), unison
    # pairs (PAIRED) and a brass plectrum (pick); every number is sound design
    CatalogEntry(
        'tar',
        'Tar (Persian)',
        Family.PLUCKED_STRINGS,
        'C3',
        'G5',
        partial(
            _plucked,
            ring_seconds=1.0,
            low_pass=7000.0,
            slope=3.5,
            position=0.1,
            courses=PAIRED,
            pick=0.08,
        ),
    ),
    # Sound and range: https://en.wikipedia.org/wiki/Tiple_colombiano ("plucked, metal string
    # chordophones usually played with a pick"; "Its twelve strings are arranged in four groups
    # of three"; "The outer two strings of each of course is tuned an octave higher than the
    # middle string in the course"; "This arrangement produces the set of harmonics that gives
    # the instrument its unique voice"; "An 18 or 19 fret fingerboard gives the tiple Colombiano
    # a range of about 2-2/3 octaves, from C3 - G#5 (or A5)", the 19-fret top A5). Two octave
    # courses, slightly detuned against each other: as with the twelve string guitar, the
    # courses double every note, though the top course is unison on the instrument. Every number
    # is sound design
    CatalogEntry(
        'tiple colombiano',
        'Tiple (Colombian)',
        Family.PLUCKED_STRINGS,
        'C3',
        'A5',
        partial(
            _plucked,
            ring_seconds=2.0,
            low_pass=6500.0,
            slope=5.0,
            position=0.15,
            courses=(
                Course(semitones=12.0, cents=2.0, level=0.8),
                Course(semitones=12.0, cents=-3.0, level=0.8),
            ),
            pick=0.04,
        ),
    ),
)

# The family: its builds, then the sound-alikes that share them (``plucked_sound_alikes.py``)
PLUCKED_STRINGS: Final[tuple[CatalogEntry, ...]] = _PLUCKED_BUILDS + PLUCKED_SOUND_ALIKES
