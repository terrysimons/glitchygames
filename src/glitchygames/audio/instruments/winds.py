"""Woodwinds: clarinets, saxophones and free reeds.

The flutes are in the sibling module ``flutes.py``, the double reeds in ``double_reeds.py``, the
bagpipes in ``bagpipes.py``.

Ranges are sounding pitch (a B-flat clarinet's written C sounds B-flat), after the standard
orchestration ranges (Adler, *The Study of Orchestration*; Vienna Symphonic Library's instrument
pages); folk instruments' are typical of the common keys. Timbres follow the instruments'
acoustics: a clarinet (a closed cylinder) favours odd harmonics, saxophones (cones) have every
harmonic and are brighter, free reeds are bright and buzzy.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import blown, falling_series

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
