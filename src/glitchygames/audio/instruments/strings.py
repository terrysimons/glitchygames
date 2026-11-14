"""Struck strings: hammered dulcimer, cimbalom, santur, yangqin and the berimbau.

Harps are in the sibling module ``harps.py``, bowed strings (violins, viols, fiddles) in
``bowed_strings.py``, plucked strings (guitars, basses, lutes) in ``plucked_strings.py``.

Ranges are sounding pitch, after the common tunings of the instruments. Timbres: a hammered
dulcimer is a plucked string's series (``plucked_series``) plucked near the string's end, with two
slightly detuned courses; the berimbau is ``struck``.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import Course, Partial, plucked, plucked_series, struck

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

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
