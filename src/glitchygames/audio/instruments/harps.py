"""Harps: concert, lever, wire-strung and triple harps, the lyre, kora and harp guitar.

A harp's strings run in a plane perpendicular to the soundboard (Hornbostel-Sachs 322); the kora is
a harp-lute (323). The family's sound-alikes, listed instruments that share another entry's build,
are in ``harp_sound_alikes.py``. Struck strings (dulcimers) are in the sibling module
``struck_strings.py``, bowed strings in ``bowed_strings.py``, plucked strings in
``plucked_strings.py``.

Ranges are sounding pitch, after the common tunings of the instruments. Timbres: a harp string
is plucked and rings down (``plucked_series``).
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.harp_sound_alikes import HARP_SOUND_ALIKES
from glitchygames.audio.instruments.timbres import plucked, plucked_series

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


_HARP_BUILDS: Final[tuple[CatalogEntry, ...]] = (
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

HARPS: Final[tuple[CatalogEntry, ...]] = _HARP_BUILDS + HARP_SOUND_ALIKES
