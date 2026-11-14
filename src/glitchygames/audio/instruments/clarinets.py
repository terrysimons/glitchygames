"""Clarinets: cylindrical single reeds, E-flat to contrabass clarinet, basset horn and chalumeau.

Ranges are sounding pitch (a B-flat clarinet's written C sounds B-flat), after the standard
orchestration ranges (Adler, *The Study of Orchestration*; Vienna Symphonic Library's instrument
pages). The timbre follows the instrument's acoustics: a clarinet (a closed cylinder) favours odd
harmonics. A single reed on a conical bore is a saxophone, not a clarinet. The family's
sound-alikes, listed instruments that share another entry's build, are in
``clarinet_sound_alikes.py``. The saxophones and the free reeds are in the sibling module
``winds.py``.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.clarinet_sound_alikes import CLARINET_SOUND_ALIKES
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


_CLARINET_BUILDS: Final[tuple[CatalogEntry, ...]] = (
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

CLARINETS: Final[tuple[CatalogEntry, ...]] = _CLARINET_BUILDS + CLARINET_SOUND_ALIKES
