"""Strings: bowed, harps and struck strings (dulcimers).

Plucked strings (guitars, basses, lutes) are in the sibling module ``plucked_strings.py``.

Ranges are sounding pitch (a double bass sounds an octave below written), after the standard
orchestration ranges (Adler, *The Study of Orchestration*) and the common tunings of folk
instruments. Timbres: a bowed string is sawtooth-like (the bow's stick-slip motion; Helmholtz)
with bow noise.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import (
    Course,
    Partial,
    blown,
    falling_series,
    plucked,
    plucked_series,
    struck,
)

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

# --- Bowed strings --------------------------------------------------------------------------


def _bowed(  # ruff: ignore[too-many-arguments] - the bowed family's traits
    *,
    low_pass: float,
    attack: float = 0.06,
    slope: float = 5.5,
    section_cents: float = 0.0,
    bow_noise: float = 0.012,
    drive: float = 0.0,
) -> Instrument:
    return blown(
        falling_series(count=28, decibels_per_octave=slope),
        attack=attack,
        release=0.15,
        breath=bow_noise,
        breath_low_pass=6000.0,
        low_pass=low_pass,
        chorus_cents=section_cents,
        drive=drive,
    )


def _pizzicato(*, ring_seconds: float, low_pass: float) -> Instrument:
    return plucked(
        plucked_series(count=16, decibels_per_octave=7.0, pluck_position=0.3),
        ring_seconds=ring_seconds,
        release=0.15,
        low_pass=low_pass,
    )


VIOLIN = partial(_bowed, low_pass=7000.0)
VIOLA = partial(_bowed, low_pass=5000.0, slope=6.0)
CELLO = partial(_bowed, low_pass=4000.0, slope=6.0, attack=0.07)
DOUBLE_BASS = partial(_bowed, low_pass=2500.0, slope=6.5, attack=0.09)
VIOL = partial(_bowed, low_pass=4500.0, slope=7.0, attack=0.05, bow_noise=0.02)
FOLK_FIDDLE = partial(_bowed, low_pass=7500.0, slope=4.5, attack=0.035, bow_noise=0.02)
SPIKE_FIDDLE = partial(_bowed, low_pass=6000.0, slope=5.0, attack=0.05, bow_noise=0.025)

BOWED_STRINGS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry('violin', 'Violin', Family.BOWED_STRINGS, 'G3', 'E7', VIOLIN),
    CatalogEntry('viola', 'Viola', Family.BOWED_STRINGS, 'C3', 'E6', VIOLA),
    CatalogEntry('cello', 'Cello', Family.BOWED_STRINGS, 'C2', 'A5', CELLO),
    CatalogEntry('double bass', 'Double bass', Family.BOWED_STRINGS, 'E1', 'G4', DOUBLE_BASS),
    CatalogEntry(
        'five string double bass',
        'Five-string double bass',
        Family.BOWED_STRINGS,
        'B0',
        'G4',
        DOUBLE_BASS,
    ),
    CatalogEntry(
        'violin section',
        'Violin section',
        Family.BOWED_STRINGS,
        'G3',
        'E7',
        partial(_bowed, low_pass=6500.0, attack=0.12, section_cents=9.0),
    ),
    CatalogEntry(
        'viola section',
        'Viola section',
        Family.BOWED_STRINGS,
        'C3',
        'E6',
        partial(_bowed, low_pass=4800.0, slope=6.0, attack=0.13, section_cents=8.0),
    ),
    CatalogEntry(
        'cello section',
        'Cello section',
        Family.BOWED_STRINGS,
        'C2',
        'A5',
        partial(_bowed, low_pass=3800.0, slope=6.0, attack=0.14, section_cents=7.0),
    ),
    CatalogEntry(
        'double bass section',
        'Double bass section',
        Family.BOWED_STRINGS,
        'E1',
        'G4',
        partial(_bowed, low_pass=2400.0, slope=6.5, attack=0.15, section_cents=6.0),
    ),
    CatalogEntry(
        'violin pizzicato',
        'Violin pizzicato',
        Family.BOWED_STRINGS,
        'G3',
        'E6',
        partial(_pizzicato, ring_seconds=0.35, low_pass=5000.0),
    ),
    CatalogEntry(
        'viola pizzicato',
        'Viola pizzicato',
        Family.BOWED_STRINGS,
        'C3',
        'C6',
        partial(_pizzicato, ring_seconds=0.45, low_pass=4000.0),
    ),
    CatalogEntry(
        'cello pizzicato',
        'Cello pizzicato',
        Family.BOWED_STRINGS,
        'C2',
        'A4',
        partial(_pizzicato, ring_seconds=0.7, low_pass=3000.0),
    ),
    CatalogEntry(
        'double bass pizzicato',
        'Double bass pizzicato',
        Family.BOWED_STRINGS,
        'E1',
        'G3',
        partial(_pizzicato, ring_seconds=1.0, low_pass=1800.0),
    ),
    CatalogEntry(
        'violin sul ponticello',
        'Violin, sul ponticello',
        Family.BOWED_STRINGS,
        'G3',
        'E7',
        partial(_bowed, low_pass=9000.0, slope=2.5, bow_noise=0.03),
    ),
    CatalogEntry('fiddle', 'Folk fiddle', Family.BOWED_STRINGS, 'G3', 'E6', FOLK_FIDDLE),
    CatalogEntry(
        'hardanger fiddle',
        'Hardanger fiddle',
        Family.BOWED_STRINGS,
        'A3',
        'E6',
        partial(
            _bowed, low_pass=7500.0, slope=4.5, attack=0.035, bow_noise=0.02, section_cents=4.0
        ),
    ),
    CatalogEntry('treble viol', 'Treble viol', Family.BOWED_STRINGS, 'D3', 'D6', VIOL),
    CatalogEntry('tenor viol', 'Tenor viol', Family.BOWED_STRINGS, 'G2', 'G5', VIOL),
    CatalogEntry('bass viol', 'Bass viol (viola da gamba)', Family.BOWED_STRINGS, 'D2', 'D5', VIOL),
    CatalogEntry('violone', 'Violone', Family.BOWED_STRINGS, 'G1', 'G4', VIOL),
    CatalogEntry(
        'viola d amore',
        "Viola d'amore",
        Family.BOWED_STRINGS,
        'A2',
        'A6',
        partial(_bowed, low_pass=5500.0, slope=5.5, section_cents=3.0),
    ),
    CatalogEntry(
        'nyckelharpa',
        'Nyckelharpa',
        Family.BOWED_STRINGS,
        'C3',
        'C6',
        partial(_bowed, low_pass=6000.0, slope=5.0, section_cents=5.0, bow_noise=0.02),
    ),
    CatalogEntry('erhu', 'Erhu', Family.BOWED_STRINGS, 'D4', 'D7', SPIKE_FIDDLE),
    CatalogEntry('morin khuur', 'Morin khuur', Family.BOWED_STRINGS, 'F2', 'C5', SPIKE_FIDDLE),
    CatalogEntry(
        'sarangi',
        'Sarangi',
        Family.BOWED_STRINGS,
        'A3',
        'C6',
        partial(_bowed, low_pass=6000.0, slope=5.0, section_cents=6.0, bow_noise=0.02),
    ),
    CatalogEntry('kemenche', 'Kemenche', Family.BOWED_STRINGS, 'A3', 'A6', SPIKE_FIDDLE),
    CatalogEntry(
        'hurdy gurdy',
        'Hurdy-gurdy',
        Family.BOWED_STRINGS,
        'G3',
        'G5',
        partial(_bowed, low_pass=5000.0, slope=3.5, attack=0.03, bow_noise=0.03, drive=1.2),
    ),
)

# --- Harps ----------------------------------------------------------------------------------


def _harp(*, ring_seconds: float, low_pass: float, slope: float = 8.0) -> Instrument:
    return plucked(
        plucked_series(count=20, decibels_per_octave=slope, pluck_position=0.5 - 0.17),
        ring_seconds=ring_seconds,
        release=0.8,
        low_pass=low_pass,
    )


HARPS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'concert harp',
        'Concert (pedal) harp',
        Family.HARPS,
        'Cb1',
        'G#7',
        partial(_harp, ring_seconds=4.0, low_pass=4500.0),
    ),
    CatalogEntry(
        'celtic harp',
        'Celtic (lever) harp',
        Family.HARPS,
        'C2',
        'A6',
        partial(_harp, ring_seconds=3.0, low_pass=5000.0, slope=7.0),
    ),
    CatalogEntry(
        'wire strung harp',
        'Wire-strung harp (clàrsach)',
        Family.HARPS,
        'G1',
        'D6',
        partial(_harp, ring_seconds=6.0, low_pass=7000.0, slope=5.0),
    ),
    CatalogEntry(
        'triple harp',
        'Welsh triple harp',
        Family.HARPS,
        'C2',
        'C7',
        partial(_harp, ring_seconds=3.0, low_pass=5000.0, slope=7.0),
    ),
    CatalogEntry(
        'lyre',
        'Lyre',
        Family.HARPS,
        'C4',
        'C6',
        partial(_harp, ring_seconds=2.0, low_pass=5000.0, slope=6.5),
    ),
    CatalogEntry(
        'kora',
        'Kora',
        Family.HARPS,
        'F2',
        'C6',
        partial(_harp, ring_seconds=2.2, low_pass=6500.0, slope=5.0),
    ),
    CatalogEntry(
        'harp guitar',
        'Harp guitar',
        Family.HARPS,
        'A1',
        'C6',
        partial(_harp, ring_seconds=3.5, low_pass=5000.0, slope=6.0),
    ),
)

# --- Struck strings -------------------------------------------------------------------------


def _hammered(*, ring_seconds: float, low_pass: float) -> Instrument:
    return plucked(
        plucked_series(count=24, decibels_per_octave=4.0, pluck_position=0.12),
        ring_seconds=ring_seconds,
        release=min(1.2, ring_seconds),
        courses=(Course(cents=4.0), Course(cents=-3.0, level=0.6)),
        low_pass=low_pass,
    )


def _berimbau() -> Instrument:
    # A struck bow over a gourd: a buzzy fundamental and a resonance near the fourth harmonic
    return struck(
        (
            Partial(ratio=1.0, level=1.0, ring_seconds=0.8, wave='saw'),
            Partial(ratio=4.0, level=0.4, ring_seconds=0.3),
            Partial(ratio=6.0, level=0.15, ring_seconds=0.15),
        ),
        release=0.6,
        mallet=0.2,
        mallet_low_pass=5000.0,
    )


STRUCK_STRINGS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'hammered dulcimer',
        'Hammered dulcimer',
        Family.STRUCK_STRINGS,
        'D3',
        'E6',
        partial(_hammered, ring_seconds=3.0, low_pass=7000.0),
    ),
    CatalogEntry(
        'cimbalom',
        'Cimbalom',
        Family.STRUCK_STRINGS,
        'E2',
        'A6',
        partial(_hammered, ring_seconds=3.5, low_pass=6000.0),
    ),
    CatalogEntry(
        'santur',
        'Santur',
        Family.STRUCK_STRINGS,
        'E3',
        'F6',
        partial(_hammered, ring_seconds=2.5, low_pass=7500.0),
    ),
    CatalogEntry(
        'yangqin',
        'Yangqin',
        Family.STRUCK_STRINGS,
        'G2',
        'A6',
        partial(_hammered, ring_seconds=2.5, low_pass=7000.0),
    ),
    CatalogEntry('berimbau', 'Berimbau', Family.STRUCK_STRINGS, 'A2', 'C3', _berimbau),
)
