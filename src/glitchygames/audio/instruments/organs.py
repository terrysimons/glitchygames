"""Organs: pipe organ stops, positive, combo and theatre organs, and the calliope.

Organs are drawbar registrations (``Harmonics.drawbars``) or pipe stops: a principal's every
harmonic, a flute stop's nearly pure tone, a reed stop's brassy one. Ranges are an organ's keys at
8' pitch (a 61-note manual, C2-C7), and a 16' stop or drawbar sounds an octave lower. A stop
sounds at its footage against its keys (16' an octave below, 4' an octave above, 2 2/3' a twelfth
above), through ``_pipe_stop``'s ``footage``. A self-playing organ carries ``Tag.MECHANICAL``. The
sound-alikes are in ``organ_sound_alikes.py``; the keyboards and electromechanical instruments are
in ``keyboards.py``.
"""

from __future__ import annotations

import math
from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.organ_sound_alikes import ORGAN_SOUND_ALIKES
from glitchygames.audio.instruments.timbres import blown, drawbar_organ, falling_series

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument


# A stop of 8' sounds at its key's pitch
UNISON_FOOTAGE: Final[float] = 8.0


def _pipe_stop(
    levels: tuple[float, ...],
    *,
    chiff: float,
    release: float = 0.15,
    footage: float = UNISON_FOOTAGE,
) -> Instrument:
    # The tone sounds at its footage against the key (16' an octave below, 4' an octave above);
    # the chiff is breath noise and stays
    return blown(
        levels,
        attack=0.04,
        release=release,
        breath=chiff,
        breath_low_pass=6000.0,
        semitones=12.0 * math.log2(UNISON_FOOTAGE / footage),
    )


PRINCIPAL_LEVELS: Final[tuple[float, ...]] = falling_series(count=16, decibels_per_octave=6.5)
FLUTE_STOP_LEVELS: Final[tuple[float, ...]] = (1.0, 0.1, 0.12, 0.02, 0.02)
REED_STOP_LEVELS: Final[tuple[float, ...]] = falling_series(count=28, decibels_per_octave=2.5)
STRING_STOP_LEVELS: Final[tuple[float, ...]] = falling_series(count=28, decibels_per_octave=4.0)
CALLIOPE_LEVELS: Final[tuple[float, ...]] = (1.0, 0.25, 0.2, 0.05)

_ORGAN_BUILDS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'pipe organ principal',
        "Pipe organ, principal 8'",
        Family.ORGANS,
        'C2',
        'C7',
        partial(_pipe_stop, PRINCIPAL_LEVELS, chiff=0.01),
    ),
    CatalogEntry(
        'pipe organ flute',
        "Pipe organ, flute 8'",
        Family.ORGANS,
        'C2',
        'C7',
        partial(_pipe_stop, FLUTE_STOP_LEVELS, chiff=0.02),
    ),
    CatalogEntry(
        'pipe organ reed',
        "Pipe organ, trumpet 8'",
        Family.ORGANS,
        'C2',
        'C7',
        partial(_pipe_stop, REED_STOP_LEVELS, chiff=0.0),
    ),
    CatalogEntry(
        'pipe organ string',
        "Pipe organ, viola da gamba 8'",
        Family.ORGANS,
        'C2',
        'C7',
        partial(_pipe_stop, STRING_STOP_LEVELS, chiff=0.0),
    ),
    CatalogEntry(
        'pipe organ plenum',
        'Pipe organ, full (plenum)',
        Family.ORGANS,
        'C2',
        'C7',
        partial(drawbar_organ, '868868868', attack=0.04, release=0.3),
    ),
    CatalogEntry(
        'positive organ',
        'Positive organ',
        Family.ORGANS,
        'C2',
        'C6',
        partial(drawbar_organ, '008505000', attack=0.03, release=0.1),
    ),
    CatalogEntry(
        'combo organ',
        'Combo organ',
        Family.ORGANS,
        'C2',
        'C7',
        partial(
            blown,
            falling_series(count=20, decibels_per_octave=3.0, even_level=0.3),
            attack=0.003,
            release=0.03,
        ),
    ),
    CatalogEntry(
        'theatre organ',
        'Theatre organ (tibia)',
        Family.ORGANS,
        'C2',
        'C7',
        partial(blown, FLUTE_STOP_LEVELS, attack=0.03, release=0.2, chorus_cents=6.0),
    ),
    CatalogEntry(
        'calliope',
        'Calliope',
        Family.ORGANS,
        'C3',
        'G5',
        partial(
            blown, CALLIOPE_LEVELS, attack=0.02, release=0.1, breath=0.05, breath_low_pass=7000.0
        ),
    ),
)

ORGANS: Final[tuple[CatalogEntry, ...]] = _ORGAN_BUILDS + ORGAN_SOUND_ALIKES
