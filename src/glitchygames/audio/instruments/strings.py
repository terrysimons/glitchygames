"""Strings: harps and struck strings (dulcimers).

Bowed strings (violins, viols, fiddles) are in the sibling module ``bowed_strings.py``, plucked
strings (guitars, basses, lutes) in ``plucked_strings.py``.

Ranges are sounding pitch, after the common tunings of the instruments. Timbres: a harp string
is plucked and rings down (``plucked_series``); a hammered dulcimer's courses are struck and
paired.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import Course, Partial, plucked, plucked_series, struck

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

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
