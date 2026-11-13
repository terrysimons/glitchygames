"""Free reeds: accordions, concertinas, bandoneon, harmonium, harmonicas, melodicas and sheng.

A free reed is a tongue swinging through a closely fitting slot (Hornbostel-Sachs 412.13). The
family's sound-alikes, listed instruments that share another entry's build, are in
``free_reed_sound_alikes.py``. The saxophones are in the sibling module ``winds.py``.

Ranges are sounding pitch, after the standard orchestration ranges (Adler, *The Study of
Orchestration*; Vienna Symphonic Library's instrument pages); folk instruments' are typical of the
common keys. Timbres follow the instruments' acoustics: free reeds are bright and buzzy.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.free_reed_sound_alikes import FREE_REED_SOUND_ALIKES
from glitchygames.audio.instruments.timbres import blown, falling_series

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

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


_FREE_REED_BUILDS: Final[tuple[CatalogEntry, ...]] = (
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

FREE_REEDS: Final[tuple[CatalogEntry, ...]] = _FREE_REED_BUILDS + FREE_REED_SOUND_ALIKES
