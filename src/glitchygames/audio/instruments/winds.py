"""Woodwinds: clarinets, saxophones, double reeds, bagpipes and free reeds.

The flutes are in the sibling module ``flutes.py``.

Ranges are sounding pitch (a B-flat clarinet's written C sounds B-flat), after the standard
orchestration ranges (Adler, *The Study of Orchestration*; Vienna Symphonic Library's instrument
pages); folk instruments' are typical of the common keys. Timbres follow the instruments'
acoustics: a clarinet (a closed cylinder) favours odd harmonics, saxophones and double reeds
(cones) have every harmonic and are brighter, free reeds are bright and buzzy, a bagpipe's
chanter sounds over fixed drones.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import (
    blown,
    falling_series,
    wave_from_levels,
    with_drones,
)

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

# --- Clarinets ------------------------------------------------------------------------------


def _clarinet(*, slope: float, low_pass: float) -> Instrument:
    # A closed cylinder: odd harmonics, with only a trace of the even ones
    return blown(
        falling_series(count=16, decibels_per_octave=slope, even_level=0.1),
        attack=0.025,
        release=0.07,
        breath=0.012,
        low_pass=low_pass,
    )


CLARINETS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'e flat clarinet',
        'E-flat clarinet',
        Family.CLARINETS,
        'G3',
        'C7',
        partial(_clarinet, slope=4.0, low_pass=7000.0),
    ),
    CatalogEntry(
        'clarinet',
        'B-flat clarinet',
        Family.CLARINETS,
        'D3',
        'Bb6',
        partial(_clarinet, slope=5.0, low_pass=5500.0),
    ),
    CatalogEntry(
        'a clarinet',
        'A clarinet',
        Family.CLARINETS,
        'C#3',
        'A6',
        partial(_clarinet, slope=5.5, low_pass=5000.0),
    ),
    CatalogEntry(
        'basset horn',
        'Basset horn',
        Family.CLARINETS,
        'F2',
        'F5',
        partial(_clarinet, slope=6.5, low_pass=4000.0),
    ),
    CatalogEntry(
        'alto clarinet',
        'Alto clarinet',
        Family.CLARINETS,
        'G2',
        'Bb5',
        partial(_clarinet, slope=6.5, low_pass=3800.0),
    ),
    CatalogEntry(
        'bass clarinet',
        'Bass clarinet',
        Family.CLARINETS,
        'Bb1',
        'F5',
        partial(_clarinet, slope=7.0, low_pass=3000.0),
    ),
    CatalogEntry(
        'contra alto clarinet',
        'Contra-alto clarinet',
        Family.CLARINETS,
        'Gb1',
        'G4',
        partial(_clarinet, slope=7.5, low_pass=2500.0),
    ),
    CatalogEntry(
        'contrabass clarinet',
        'Contrabass clarinet',
        Family.CLARINETS,
        'Bb0',
        'Bb3',
        partial(_clarinet, slope=8.0, low_pass=2000.0),
    ),
    CatalogEntry(
        'chalumeau',
        'Chalumeau',
        Family.CLARINETS,
        'F3',
        'Bb4',
        partial(_clarinet, slope=8.0, low_pass=3000.0),
    ),
)

# --- Saxophones -----------------------------------------------------------------------------


def _saxophone(*, low_pass: float) -> Instrument:
    # A cone: every harmonic, bright, with an edge on the attack
    return blown(
        falling_series(count=18, decibels_per_octave=4.5),
        attack=0.03,
        release=0.08,
        breath=0.02,
        breath_low_pass=6000.0,
        low_pass=low_pass,
        drive=0.6,
        bite_levels=falling_series(count=24, decibels_per_octave=2.0),
    )


SAXOPHONES: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'sopranino saxophone',
        'Sopranino saxophone',
        Family.SAXOPHONES,
        'Db4',
        'Ab6',
        partial(_saxophone, low_pass=8000.0),
    ),
    CatalogEntry(
        'soprano saxophone',
        'Soprano saxophone',
        Family.SAXOPHONES,
        'Ab3',
        'Eb6',
        partial(_saxophone, low_pass=7000.0),
    ),
    CatalogEntry(
        'alto saxophone',
        'Alto saxophone',
        Family.SAXOPHONES,
        'Db3',
        'Ab5',
        partial(_saxophone, low_pass=6000.0),
    ),
    CatalogEntry(
        'c melody saxophone',
        'C melody saxophone',
        Family.SAXOPHONES,
        'Bb2',
        'F5',
        partial(_saxophone, low_pass=5500.0),
    ),
    CatalogEntry(
        'tenor saxophone',
        'Tenor saxophone',
        Family.SAXOPHONES,
        'Ab2',
        'Eb5',
        partial(_saxophone, low_pass=5000.0),
    ),
    CatalogEntry(
        'baritone saxophone',
        'Baritone saxophone',
        Family.SAXOPHONES,
        'C2',
        'Ab4',
        partial(_saxophone, low_pass=4000.0),
    ),
    CatalogEntry(
        'bass saxophone',
        'Bass saxophone',
        Family.SAXOPHONES,
        'Ab1',
        'Eb4',
        partial(_saxophone, low_pass=3200.0),
    ),
    CatalogEntry(
        'contrabass saxophone',
        'Contrabass saxophone',
        Family.SAXOPHONES,
        'Db1',
        'Ab3',
        partial(_saxophone, low_pass=2500.0),
    ),
)

# --- Double reeds ---------------------------------------------------------------------------

# An oboe's nasal colour: the second to fourth harmonics louder than the fundamental
OBOE_LEVELS: Final[tuple[float, ...]] = (
    0.55,
    1.0,
    0.9,
    0.7,
    0.5,
    0.42,
    0.3,
    0.22,
    0.16,
    0.12,
    0.08,
    0.06,
)
BASSOON_LEVELS: Final[tuple[float, ...]] = (1.0, 0.9, 0.75, 0.65, 0.5, 0.35, 0.26, 0.18, 0.12, 0.08)


def _double_reed(levels: tuple[float, ...], *, low_pass: float, drive: float = 0.4) -> Instrument:
    return blown(levels, attack=0.025, release=0.06, breath=0.01, low_pass=low_pass, drive=drive)


def _folk_shawm(*, low_pass: float) -> Instrument:
    # Shawms and their cousins (suona, zurna, bombarde): loud, bright, hard-driven reeds
    return blown(
        falling_series(count=24, decibels_per_octave=2.0),
        attack=0.02,
        release=0.05,
        breath=0.015,
        low_pass=low_pass,
        drive=1.6,
    )


def _capped_reed(*, low_pass: float) -> Instrument:
    # A capped cylinder (the crumhorn): odd harmonics only, buzzy
    return blown(
        falling_series(count=20, decibels_per_octave=2.5, odd_only=True),
        attack=0.015,
        release=0.04,
        low_pass=low_pass,
        drive=1.0,
    )


def _duduk() -> Instrument:
    return blown(
        falling_series(count=10, decibels_per_octave=9.0),
        attack=0.07,
        release=0.12,
        breath=0.04,
        breath_low_pass=3000.0,
        low_pass=3500.0,
    )


DOUBLE_REEDS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'oboe',
        'Oboe',
        Family.DOUBLE_REEDS,
        'Bb3',
        'A6',
        partial(_double_reed, OBOE_LEVELS, low_pass=7000.0),
    ),
    CatalogEntry(
        'oboe d amore',
        "Oboe d'amore",
        Family.DOUBLE_REEDS,
        'G#3',
        'C#6',
        partial(_double_reed, OBOE_LEVELS, low_pass=5500.0),
    ),
    CatalogEntry(
        'english horn',
        'English horn (cor anglais)',
        Family.DOUBLE_REEDS,
        'E3',
        'C6',
        partial(_double_reed, OBOE_LEVELS, low_pass=4500.0),
    ),
    CatalogEntry(
        'bass oboe',
        'Bass oboe',
        Family.DOUBLE_REEDS,
        'B2',
        'G5',
        partial(_double_reed, OBOE_LEVELS, low_pass=3800.0),
    ),
    CatalogEntry(
        'heckelphone',
        'Heckelphone',
        Family.DOUBLE_REEDS,
        'A2',
        'F5',
        partial(_double_reed, OBOE_LEVELS, low_pass=3500.0, drive=0.8),
    ),
    CatalogEntry(
        'bassoon',
        'Bassoon',
        Family.DOUBLE_REEDS,
        'Bb1',
        'E5',
        partial(_double_reed, BASSOON_LEVELS, low_pass=3500.0),
    ),
    CatalogEntry(
        'contrabassoon',
        'Contrabassoon',
        Family.DOUBLE_REEDS,
        'Bb0',
        'Bb3',
        partial(_double_reed, BASSOON_LEVELS, low_pass=2200.0),
    ),
    CatalogEntry(
        'sarrusophone',
        'Contrabass sarrusophone in C',
        Family.DOUBLE_REEDS,
        'Bb0',
        'G3',
        partial(_double_reed, BASSOON_LEVELS, low_pass=2500.0, drive=1.2),
    ),
    CatalogEntry(
        'soprano shawm',
        'Soprano shawm',
        Family.DOUBLE_REEDS,
        'D4',
        'B5',
        partial(_folk_shawm, low_pass=8000.0),
    ),
    CatalogEntry(
        'alto shawm',
        'Alto shawm',
        Family.DOUBLE_REEDS,
        'G3',
        'E5',
        partial(_folk_shawm, low_pass=6500.0),
    ),
    CatalogEntry(
        'tenor shawm',
        'Tenor shawm',
        Family.DOUBLE_REEDS,
        'C3',
        'A4',
        partial(_folk_shawm, low_pass=5000.0),
    ),
    CatalogEntry(
        'bass shawm',
        'Bass shawm',
        Family.DOUBLE_REEDS,
        'F2',
        'D4',
        partial(_folk_shawm, low_pass=4000.0),
    ),
    CatalogEntry(
        'suona', 'Suona', Family.DOUBLE_REEDS, 'D4', 'D6', partial(_folk_shawm, low_pass=8000.0)
    ),
    CatalogEntry(
        'zurna', 'Zurna', Family.DOUBLE_REEDS, 'C4', 'C6', partial(_folk_shawm, low_pass=8000.0)
    ),
    CatalogEntry(
        'bombarde',
        'Bombarde',
        Family.DOUBLE_REEDS,
        'Bb4',
        'C6',
        partial(_folk_shawm, low_pass=8000.0),
    ),
    CatalogEntry(
        'hichiriki',
        'Hichiriki',
        Family.DOUBLE_REEDS,
        'E4',
        'A5',
        partial(_folk_shawm, low_pass=6000.0),
    ),
    CatalogEntry(
        'piri', 'Piri', Family.DOUBLE_REEDS, 'Eb4', 'Bb5', partial(_folk_shawm, low_pass=6000.0)
    ),
    CatalogEntry(
        'soprano crumhorn',
        'Soprano crumhorn',
        Family.DOUBLE_REEDS,
        'C4',
        'D5',
        partial(_capped_reed, low_pass=5000.0),
    ),
    CatalogEntry(
        'alto crumhorn',
        'Alto crumhorn',
        Family.DOUBLE_REEDS,
        'F3',
        'G4',
        partial(_capped_reed, low_pass=4200.0),
    ),
    CatalogEntry(
        'tenor crumhorn',
        'Tenor crumhorn',
        Family.DOUBLE_REEDS,
        'C3',
        'D4',
        partial(_capped_reed, low_pass=3500.0),
    ),
    CatalogEntry(
        'bass crumhorn',
        'Bass crumhorn',
        Family.DOUBLE_REEDS,
        'F2',
        'G3',
        partial(_capped_reed, low_pass=2800.0),
    ),
    CatalogEntry(
        'rackett',
        'Rackett',
        Family.DOUBLE_REEDS,
        'C2',
        'C4',
        partial(_capped_reed, low_pass=2000.0),
    ),
    CatalogEntry('duduk', 'Duduk', Family.DOUBLE_REEDS, 'G3', 'C5', _duduk),
)

# --- Bagpipes -------------------------------------------------------------------------------

# The Highland and uilleann timbres are scripts/make_pipes.py's, tuned there by ear
HIGHLAND_LEVELS: Final[tuple[float, ...]] = (
    1.0,
    0.95,
    0.85,
    0.8,
    0.75,
    0.65,
    0.55,
    0.5,
    0.42,
    0.36,
    0.3,
    0.25,
)
DRONE_LEVELS: Final[tuple[float, ...]] = (1.0, 0.7, 0.55, 0.4, 0.3, 0.22, 0.15, 0.1)
SWEET_CHANTER_LEVELS: Final[tuple[float, ...]] = (1.0, 0.55, 0.4, 0.26, 0.17, 0.1, 0.06, 0.035)
SMOOTH_DRONE_LEVELS: Final[tuple[float, ...]] = (1.0, 0.3, 0.12, 0.05)


def _bagpipe(  # ruff: ignore[too-many-arguments] - a chanter's traits and its drones
    *,
    chanter_levels: tuple[float, ...],
    drones: tuple[tuple[float, float], ...],
    drone_levels: tuple[float, ...],
    low_pass: float,
    drive: float,
    breath: float,
    attack: float = 0.006,
    sustain: float = 1.0,
) -> Instrument:
    chanter = blown(
        chanter_levels,
        attack=attack,
        decay=0.04 if sustain < 1.0 else 0.0,
        sustain=sustain,
        release=0.03,
        breath=breath,
        breath_low_pass=4500.0,
        low_pass=low_pass,
        drive=drive,
    )
    return with_drones(chanter, drones=drones, drone_wave=wave_from_levels(drone_levels))


BAGPIPES: Final[tuple[CatalogEntry, ...]] = (
    # Chanter A near 480 Hz (pipers tune sharp); tenor drones an octave below, bass two
    CatalogEntry(
        'highland bagpipe',
        'Great Highland bagpipe',
        Family.BAGPIPES,
        'Ab4',
        'Bb5',
        partial(
            _bagpipe,
            chanter_levels=HIGHLAND_LEVELS,
            drones=((240.0, 0.45), (120.0, 0.55)),
            drone_levels=DRONE_LEVELS,
            low_pass=6500.0,
            drive=1.25,
            breath=0.012,
        ),
    ),
    CatalogEntry(
        'uilleann pipes',
        'Uilleann pipes',
        Family.BAGPIPES,
        'D4',
        'E6',
        partial(
            _bagpipe,
            chanter_levels=SWEET_CHANTER_LEVELS,
            drones=((146.83, 0.25), (73.42, 0.3)),
            drone_levels=SMOOTH_DRONE_LEVELS,
            low_pass=3500.0,
            drive=0.0,
            breath=0.015,
            attack=0.012,
            sustain=0.85,
        ),
    ),
    CatalogEntry(
        'scottish smallpipes',
        'Scottish smallpipes in A',
        Family.BAGPIPES,
        'G4',
        'A5',
        partial(
            _bagpipe,
            chanter_levels=SWEET_CHANTER_LEVELS,
            drones=((220.0, 0.3), (110.0, 0.35)),
            drone_levels=SMOOTH_DRONE_LEVELS,
            low_pass=4000.0,
            drive=0.3,
            breath=0.01,
        ),
    ),
    CatalogEntry(
        'border pipes',
        'Border pipes',
        Family.BAGPIPES,
        'G4',
        'A5',
        partial(
            _bagpipe,
            chanter_levels=HIGHLAND_LEVELS,
            drones=((220.0, 0.4), (110.0, 0.45)),
            drone_levels=DRONE_LEVELS,
            low_pass=5000.0,
            drive=0.8,
            breath=0.012,
        ),
    ),
    # Closed-ended: notes are detached, so the chanter drops between them
    CatalogEntry(
        'northumbrian smallpipes',
        'Northumbrian smallpipes',
        Family.BAGPIPES,
        'G4',
        'A5',
        partial(
            _bagpipe,
            chanter_levels=SWEET_CHANTER_LEVELS,
            drones=((196.0, 0.25), (98.0, 0.3)),
            drone_levels=SMOOTH_DRONE_LEVELS,
            low_pass=4500.0,
            drive=0.0,
            breath=0.008,
            attack=0.008,
            sustain=0.6,
        ),
    ),
    CatalogEntry(
        'galician gaita',
        'Galician gaita in D',
        Family.BAGPIPES,
        'C#5',
        'E6',
        partial(
            _bagpipe,
            chanter_levels=HIGHLAND_LEVELS,
            drones=((293.66, 0.3), (146.83, 0.4)),
            drone_levels=DRONE_LEVELS,
            low_pass=7000.0,
            drive=1.0,
            breath=0.012,
        ),
    ),
    CatalogEntry(
        'bulgarian gaida',
        'Bulgarian gaida',
        Family.BAGPIPES,
        'F#4',
        'A5',
        partial(
            _bagpipe,
            chanter_levels=HIGHLAND_LEVELS,
            drones=((196.0, 0.5),),
            drone_levels=DRONE_LEVELS,
            low_pass=6000.0,
            drive=1.0,
            breath=0.012,
        ),
    ),
    CatalogEntry(
        'musette de cour',
        'Musette de cour',
        Family.BAGPIPES,
        'F4',
        'D6',
        partial(
            _bagpipe,
            chanter_levels=SWEET_CHANTER_LEVELS,
            drones=((174.61, 0.2), (87.31, 0.25)),
            drone_levels=SMOOTH_DRONE_LEVELS,
            low_pass=3500.0,
            drive=0.0,
            breath=0.008,
        ),
    ),
)

# --- Free reeds -----------------------------------------------------------------------------

FREE_REED_LEVELS: Final[tuple[float, ...]] = falling_series(count=20, decibels_per_octave=3.5)


def _accordion(*, cents: float, low_pass: float) -> Instrument:
    # Musette tuning: a second reed set sharp, beating against the first
    return blown(
        FREE_REED_LEVELS,
        attack=0.03,
        release=0.06,
        breath=0.006,
        low_pass=low_pass,
        chorus_cents=cents,
    )


def _mouth_reed(*, low_pass: float, breath: float = 0.03) -> Instrument:
    return blown(
        FREE_REED_LEVELS,
        attack=0.025,
        release=0.08,
        breath=breath,
        breath_low_pass=3500.0,
        low_pass=low_pass,
        drive=0.5,
    )


FREE_REEDS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'accordion',
        'Accordion (dry)',
        Family.FREE_REEDS,
        'F3',
        'A6',
        partial(_accordion, cents=1.0, low_pass=6000.0),
    ),
    CatalogEntry(
        'musette accordion',
        'Accordion (musette)',
        Family.FREE_REEDS,
        'F3',
        'A6',
        partial(_accordion, cents=15.0, low_pass=6000.0),
    ),
    CatalogEntry(
        'accordion bass',
        'Accordion bass (Stradella)',
        Family.FREE_REEDS,
        'E1',
        'D#3',
        partial(_accordion, cents=1.0, low_pass=3000.0),
    ),
    CatalogEntry(
        'bandoneon',
        'Bandoneon',
        Family.FREE_REEDS,
        'C2',
        'A6',
        partial(_accordion, cents=3.0, low_pass=4500.0),
    ),
    CatalogEntry(
        'concertina',
        'English concertina',
        Family.FREE_REEDS,
        'G3',
        'C7',
        partial(_accordion, cents=1.0, low_pass=6500.0),
    ),
    CatalogEntry(
        'harmonium',
        'Harmonium',
        Family.FREE_REEDS,
        'C2',
        'C7',
        partial(_accordion, cents=2.0, low_pass=4000.0),
    ),
    CatalogEntry(
        'harmonica',
        'Diatonic harmonica in C',
        Family.FREE_REEDS,
        'C4',
        'C7',
        partial(_mouth_reed, low_pass=6000.0),
    ),
    CatalogEntry(
        'chromatic harmonica',
        'Chromatic harmonica',
        Family.FREE_REEDS,
        'C4',
        'D7',
        partial(_mouth_reed, low_pass=5500.0),
    ),
    CatalogEntry(
        'bass harmonica',
        'Bass harmonica',
        Family.FREE_REEDS,
        'E2',
        'E4',
        partial(_mouth_reed, low_pass=3000.0, breath=0.015),
    ),
    CatalogEntry(
        'soprano melodica',
        'Soprano melodica',
        Family.FREE_REEDS,
        'F4',
        'C7',
        partial(_mouth_reed, low_pass=6000.0),
    ),
    CatalogEntry(
        'alto melodica',
        'Alto melodica',
        Family.FREE_REEDS,
        'F3',
        'F6',
        partial(_mouth_reed, low_pass=5000.0),
    ),
    CatalogEntry(
        'bass melodica',
        'Bass melodica',
        Family.FREE_REEDS,
        'F2',
        'E4',
        partial(_mouth_reed, low_pass=3500.0),
    ),
    CatalogEntry(
        'sheng',
        'Sheng',
        Family.FREE_REEDS,
        'G3',
        'A6',
        partial(_accordion, cents=4.0, low_pass=7000.0),
    ),
)
