"""Keyboards: pianos, harpsichords, clavichord, celesta and toy piano.

A piano string is struck by a hammer near a seventh of its length, so its seventh harmonic is
nearly gone; each note has two or three slightly detuned strings, whose beating is the piano's
shimmer. A harpsichord's quill plucks near the end (bright) and has a 4' octave rank. Ranges are
each instrument's keyboard. The sound-alikes are in ``keyboard_sound_alikes.py``, the
electromechanical instruments in ``electromechanical.py`` and the pipe organ in ``organs.py``.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.keyboard_sound_alikes import KEYBOARD_SOUND_ALIKES
from glitchygames.audio.instruments.timbres import (
    Course,
    Partial,
    plucked,
    plucked_series,
    struck,
)

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

# --- Keyboards ------------------------------------------------------------------------------


def _piano(
    *, ring_seconds: float, low_pass: float, cents: float, slope: float = 6.0, hammer: float = 0.03
) -> Instrument:
    return plucked(
        plucked_series(count=24, decibels_per_octave=slope, pluck_position=1.0 / 7.0),
        ring_seconds=ring_seconds,
        release=0.25,
        courses=(Course(cents=cents, level=0.8), Course(cents=-cents / 2.0, level=0.6)),
        pick=hammer,
        pick_high_pass=1000.0,
        low_pass=low_pass,
    )


def _harpsichord(*, low_pass: float, octave_rank: bool) -> Instrument:
    courses = (Course(semitones=12.0, cents=1.0, level=0.45),) if octave_rank else ()
    return plucked(
        plucked_series(count=28, decibels_per_octave=2.5, pluck_position=0.08),
        ring_seconds=2.0,
        release=0.12,
        courses=courses,
        pick=0.04,
        pick_high_pass=3000.0,
        low_pass=low_pass,
    )


def _celesta(*, ring_seconds: float) -> Instrument:
    return struck(
        (
            Partial(ratio=1.0, level=1.0, ring_seconds=ring_seconds),
            Partial(ratio=4.0, level=0.2, ring_seconds=ring_seconds / 4.0),
        ),  # under Nyquist at C8
        release=ring_seconds / 2.0,
        mallet=0.02,
    )


def _toy_piano() -> Instrument:
    # Struck metal rods: inharmonic partials (a free bar's 1 : 2.76 : 5.40)
    return struck(
        (
            Partial(ratio=1.0, level=1.0, ring_seconds=1.2),
            Partial(ratio=2.76, level=0.5, ring_seconds=0.6),
            Partial(ratio=5.40, level=0.25, ring_seconds=0.3),
        ),
        release=0.6,
        mallet=0.05,
    )


_KEYBOARD_BUILDS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'grand piano',
        'Grand piano',
        Family.KEYBOARDS,
        'A0',
        'C8',
        partial(_piano, ring_seconds=4.5, low_pass=6000.0, cents=1.5),
    ),
    CatalogEntry(
        'bright grand piano',
        'Bright grand piano',
        Family.KEYBOARDS,
        'A0',
        'C8',
        partial(_piano, ring_seconds=4.0, low_pass=9000.0, cents=1.5, slope=4.5, hammer=0.05),
    ),
    CatalogEntry(
        'upright piano',
        'Upright piano',
        Family.KEYBOARDS,
        'A0',
        'C8',
        partial(_piano, ring_seconds=3.0, low_pass=5000.0, cents=2.5),
    ),
    CatalogEntry(
        'honky tonk piano',
        'Honky-tonk piano',
        Family.KEYBOARDS,
        'A0',
        'C8',
        partial(_piano, ring_seconds=3.0, low_pass=6000.0, cents=16.0),
    ),
    CatalogEntry(
        'fortepiano',
        'Fortepiano',
        Family.KEYBOARDS,
        'F1',
        'F6',
        partial(_piano, ring_seconds=2.0, low_pass=5500.0, cents=2.0, slope=5.0),
    ),
    CatalogEntry(
        'harpsichord',
        "Harpsichord (8' + 4')",
        Family.KEYBOARDS,
        'F1',
        'F6',
        partial(_harpsichord, low_pass=9000.0, octave_rank=True),
    ),
    CatalogEntry(
        'harpsichord lute stop',
        'Harpsichord (lute stop)',
        Family.KEYBOARDS,
        'F1',
        'F6',
        partial(_harpsichord, low_pass=3500.0, octave_rank=False),
    ),
    CatalogEntry(
        'virginal',
        'Virginal',
        Family.KEYBOARDS,
        'C2',
        'C6',
        partial(_harpsichord, low_pass=7000.0, octave_rank=False),
    ),
    CatalogEntry(
        'clavichord',
        'Clavichord',
        Family.KEYBOARDS,
        'C2',
        'E6',
        partial(_piano, ring_seconds=1.5, low_pass=5000.0, cents=1.0, slope=4.0, hammer=0.0),
    ),
    CatalogEntry(
        'celesta', 'Celesta', Family.KEYBOARDS, 'C4', 'C8', partial(_celesta, ring_seconds=1.5)
    ),
    CatalogEntry('toy piano', 'Toy piano', Family.KEYBOARDS, 'F3', 'F6', _toy_piano),
)

KEYBOARDS: Final[tuple[CatalogEntry, ...]] = _KEYBOARD_BUILDS + KEYBOARD_SOUND_ALIKES
