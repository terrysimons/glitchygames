"""Saxophones: conical single reeds, sopranino to contrabass saxophone.

The flutes are in the sibling module ``flutes.py``, the clarinets in ``clarinets.py``, the double
reeds in ``double_reeds.py``, the bagpipes in ``bagpipes.py``, the free reeds in
``free_reeds.py``.

Ranges are sounding pitch, after the standard orchestration ranges (Adler, *The Study of
Orchestration*; Vienna Symphonic Library's instrument pages); folk instruments' are typical of the
common keys. Timbres follow the instruments' acoustics: saxophones (cones) have every harmonic and
are brighter.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import blown, falling_series

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

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
