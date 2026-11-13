"""Brass: trumpets, horns, trombones, tubas, their mutes, and historic and folk lip-reeds.

Ranges are sounding pitch, after the standard orchestration ranges (Adler, *The Study of
Orchestration*); historic and folk instruments' are typical. A brass tone's brightness comes from
its bell and bore: a trumpet's harmonics fall slowly, a horn's and a tuba's fast. Each note also
starts brighter than it holds (``bite``: the lips' first buzz), and mutes reshape the spectrum (a
straight mute thins the low end, a cup mute darkens, a harmon mute leaves a nasal buzz).

The family's sound-alikes, listed instruments that share another entry's build, are in
``brass_sound_alikes.py``.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.brass_sound_alikes import BRASS_SOUND_ALIKES
from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import Formant, blown, falling_series, formant_series

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument


def _brass(  # ruff: ignore[too-many-arguments] - the brass family's traits
    *,
    slope: float,
    low_pass: float,
    attack: float = 0.035,
    release: float = 0.1,
    drive: float = 0.4,
    breath: float = 0.006,
) -> Instrument:
    return blown(
        falling_series(count=24, decibels_per_octave=slope),
        attack=attack,
        release=release,
        breath=breath,
        low_pass=low_pass,
        drive=drive,
        bite_levels=falling_series(count=28, decibels_per_octave=max(1.0, slope - 3.0)),
    )


def _muted(
    *,
    levels: tuple[float, ...],
    high_pass: float | None,
    low_pass: float | None,
    drive: float = 0.6,
) -> Instrument:
    return blown(
        levels, attack=0.03, release=0.08, low_pass=low_pass, high_pass=high_pass, drive=drive
    )


# A harmon mute: a nasal peak near 1.5-2 kHz, little fundamental
HARMON_LEVELS: Final[tuple[float, ...]] = formant_series(
    fundamental_hz=440.0,
    formants=(
        Formant(hertz=1700.0, bandwidth=700.0, decibels=0.0),
        Formant(hertz=4000.0, bandwidth=1200.0, decibels=-12.0),
    ),
    floor_decibels=-30.0,
)
STRAIGHT_MUTE_LEVELS: Final[tuple[float, ...]] = falling_series(count=24, decibels_per_octave=2.5)
CUP_MUTE_LEVELS: Final[tuple[float, ...]] = falling_series(count=12, decibels_per_octave=9.0)

TRUMPET = partial(_brass, slope=3.5, low_pass=8000.0, attack=0.025)
CORNET = partial(_brass, slope=5.0, low_pass=6000.0, attack=0.03)
FLUGELHORN = partial(_brass, slope=8.0, low_pass=3500.0, attack=0.045, drive=0.2)
HORN = partial(_brass, slope=8.5, low_pass=2800.0, attack=0.05, drive=0.2)
TENOR_BRASS = partial(_brass, slope=6.5, low_pass=3500.0, attack=0.04, drive=0.3)
TROMBONE = partial(_brass, slope=4.5, low_pass=5000.0, attack=0.035)
TUBA = partial(_brass, slope=8.0, low_pass=1800.0, attack=0.05, drive=0.2)
NATURAL = partial(_brass, slope=6.0, low_pass=4000.0, attack=0.04, drive=0.5)
WOODEN_LIP_REED = partial(_brass, slope=9.0, low_pass=2500.0, attack=0.04, drive=0.2, breath=0.015)

_BRASS_BUILDS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry('piccolo trumpet', 'Piccolo trumpet in A', Family.BRASS, 'Eb4', 'G6', TRUMPET),
    CatalogEntry('trumpet', 'B-flat trumpet', Family.BRASS, 'E3', 'C6', TRUMPET),
    CatalogEntry('c trumpet', 'C trumpet', Family.BRASS, 'F#3', 'D6', TRUMPET),
    CatalogEntry('d trumpet', 'D trumpet', Family.BRASS, 'G#3', 'E6', TRUMPET),
    CatalogEntry('bass trumpet', 'Bass trumpet', Family.BRASS, 'E2', 'Bb4', TROMBONE),
    CatalogEntry(
        'trumpet straight mute',
        'Trumpet, straight mute',
        Family.BRASS,
        'E3',
        'C6',
        partial(_muted, levels=STRAIGHT_MUTE_LEVELS, high_pass=900.0, low_pass=None),
    ),
    CatalogEntry(
        'trumpet cup mute',
        'Trumpet, cup mute',
        Family.BRASS,
        'E3',
        'C6',
        partial(_muted, levels=CUP_MUTE_LEVELS, high_pass=None, low_pass=2000.0),
    ),
    CatalogEntry(
        'trumpet harmon mute',
        'Trumpet, harmon mute',
        Family.BRASS,
        'E3',
        'C6',
        partial(_muted, levels=HARMON_LEVELS, high_pass=600.0, low_pass=None),
    ),
    CatalogEntry('cornet', 'B-flat cornet', Family.BRASS, 'E3', 'Bb5', CORNET),
    CatalogEntry('soprano cornet', 'E-flat soprano cornet', Family.BRASS, 'G3', 'Eb6', CORNET),
    CatalogEntry('flugelhorn', 'Flugelhorn', Family.BRASS, 'E3', 'Bb5', FLUGELHORN),
    CatalogEntry('bugle', 'Bugle', Family.BRASS, 'G3', 'G5', NATURAL),
    CatalogEntry('post horn', 'Post horn', Family.BRASS, 'Bb3', 'Bb5', NATURAL),
    CatalogEntry('french horn', 'French horn', Family.BRASS, 'B1', 'F5', HORN),
    CatalogEntry('descant horn', 'Descant horn', Family.BRASS, 'F2', 'C6', HORN),
    CatalogEntry(
        'french horn stopped',
        'French horn, stopped',
        Family.BRASS,
        'C3',
        'F5',
        partial(_muted, levels=STRAIGHT_MUTE_LEVELS, high_pass=700.0, low_pass=None, drive=1.5),
    ),
    CatalogEntry('natural horn', 'Natural horn', Family.BRASS, 'F2', 'F5', HORN),
    CatalogEntry('wagner tuba', 'Tenor Wagner tuba', Family.BRASS, 'E2', 'F4', HORN),
    CatalogEntry('mellophone', 'Mellophone', Family.BRASS, 'B2', 'F5', TENOR_BRASS),
    CatalogEntry('alto horn', 'E-flat alto (tenor) horn', Family.BRASS, 'A2', 'Eb5', TENOR_BRASS),
    CatalogEntry('baritone horn', 'Baritone horn', Family.BRASS, 'E2', 'Bb4', TENOR_BRASS),
    CatalogEntry(
        'euphonium',
        'Euphonium',
        Family.BRASS,
        'Bb1',
        'Bb4',
        partial(_brass, slope=7.5, low_pass=2600.0, attack=0.045, drive=0.2),
    ),
    CatalogEntry('alto trombone', 'Alto trombone', Family.BRASS, 'A2', 'Eb5', TROMBONE),
    CatalogEntry('trombone', 'Tenor trombone', Family.BRASS, 'E2', 'F5', TROMBONE),
    CatalogEntry(
        'bass trombone',
        'Bass trombone',
        Family.BRASS,
        'Bb1',
        'Bb4',
        partial(_brass, slope=5.0, low_pass=3800.0, attack=0.04),
    ),
    CatalogEntry(
        'contrabass trombone',
        'Contrabass trombone',
        Family.BRASS,
        'E1',
        'D4',
        partial(_brass, slope=5.5, low_pass=3000.0, attack=0.045),
    ),
    CatalogEntry(
        'trombone cup mute',
        'Trombone, cup mute',
        Family.BRASS,
        'E2',
        'F5',
        partial(_muted, levels=CUP_MUTE_LEVELS, high_pass=None, low_pass=1500.0),
    ),
    CatalogEntry(
        'trombone plunger',
        'Trombone, plunger mute',
        Family.BRASS,
        'E2',
        'F5',
        partial(_muted, levels=HARMON_LEVELS, high_pass=300.0, low_pass=None),
    ),
    CatalogEntry(
        'sackbut',
        'Tenor sackbut',
        Family.BRASS,
        'E2',
        'D5',
        partial(_brass, slope=7.0, low_pass=3000.0, attack=0.04, drive=0.1),
    ),
    CatalogEntry(
        'cimbasso',
        'Cimbasso',
        Family.BRASS,
        'Bb0',
        'F4',
        partial(_brass, slope=5.0, low_pass=2500.0, attack=0.045),
    ),
    CatalogEntry('f tuba', 'F tuba', Family.BRASS, 'F1', 'F4', TUBA),
    CatalogEntry('e flat tuba', 'E-flat tuba', Family.BRASS, 'Eb1', 'Eb4', TUBA),
    CatalogEntry('tuba', 'BB-flat (contrabass) tuba', Family.BRASS, 'D1', 'F4', TUBA),
    CatalogEntry(
        'sousaphone',
        'Sousaphone',
        Family.BRASS,
        'E1',
        'F4',
        partial(_brass, slope=6.5, low_pass=2400.0, attack=0.05, drive=0.3),
    ),
    CatalogEntry('cornett', 'Cornett (zink)', Family.BRASS, 'G3', 'D6', WOODEN_LIP_REED),
    CatalogEntry('serpent', 'Serpent', Family.BRASS, 'C2', 'G4', WOODEN_LIP_REED),
    CatalogEntry(
        'ophicleide',
        'Ophicleide',
        Family.BRASS,
        'B1',
        'C5',
        partial(_brass, slope=6.0, low_pass=2800.0, attack=0.04),
    ),
    CatalogEntry('alphorn', 'Alphorn in F-sharp', Family.BRASS, 'F#2', 'F#5', HORN),
    CatalogEntry(
        'shofar',
        'Shofar',
        Family.BRASS,
        'A3',
        'E4',
        partial(_brass, slope=3.0, low_pass=6000.0, attack=0.06, drive=2.0, breath=0.03),
    ),
    CatalogEntry(
        'conch',
        'Conch shell',
        Family.BRASS,
        'C4',
        'E4',
        partial(_brass, slope=7.0, low_pass=3000.0, attack=0.08, drive=0.6, breath=0.04),
    ),
    CatalogEntry(
        'didgeridoo',
        'Didgeridoo',
        Family.BRASS,
        'C2',
        'E2',
        partial(_brass, slope=4.0, low_pass=2000.0, attack=0.06, drive=2.5, breath=0.03),
    ),
    CatalogEntry(
        'vuvuzela',
        'Vuvuzela',
        Family.BRASS,
        'A3',
        'B3',
        partial(_brass, slope=2.0, low_pass=7000.0, attack=0.03, drive=3.0),
    ),
)


BRASS: Final[tuple[CatalogEntry, ...]] = _BRASS_BUILDS + BRASS_SOUND_ALIKES
