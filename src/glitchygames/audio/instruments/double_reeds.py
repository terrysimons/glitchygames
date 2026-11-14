"""Double reeds: oboes, bassoons, heckelphones, sarrusophones, shawms, capped reeds and the duduk.

The sound is made by a double reed on a conical or cylindrical pipe: Hornbostel-Sachs 422.1 (oboes,
single or in sets, capped or not). The family's sound-alikes, listed instruments that share another
entry's build, are in ``double_reed_sound_alikes.py``. The bagpipes are in the sibling module
``bagpipes.py``, the clarinets in ``clarinets.py``, the saxophones in ``saxophones.py`` and the
free reeds in ``free_reeds.py``.

Ranges are sounding pitch, after the standard orchestration ranges (Adler, *The Study of
Orchestration*; Vienna Symphonic Library's instrument pages); folk instruments' are typical of the
common keys. Timbres follow the instruments' acoustics: the conical oboes, bassoons and shawms
have every harmonic (the shawms bright and hard-driven), the capped crumhorns (cylinders) odd
harmonics only, and the duduk a soft, falling series of its own.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.double_reed_sound_alikes import DOUBLE_REED_SOUND_ALIKES
from glitchygames.audio.instruments.timbres import blown, falling_series

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

# --- Double reeds ---------------------------------------------------------------------------

# An oboe's nasal colour: the second to fourth harmonics louder than the fundamental
OBOE_LEVELS: Final[tuple[float, ...]] = (
    0.55,
    1.0,
    0.9,
    0.7,
    0.5,
    0.42,
    0.3,
    0.22,
    0.16,
    0.12,
    0.08,
    0.06,
)
BASSOON_LEVELS: Final[tuple[float, ...]] = (1.0, 0.9, 0.75, 0.65, 0.5, 0.35, 0.26, 0.18, 0.12, 0.08)


def _double_reed(levels: tuple[float, ...], *, low_pass: float, drive: float = 0.4) -> Instrument:
    return blown(levels, attack=0.025, release=0.06, breath=0.01, low_pass=low_pass, drive=drive)


def _folk_shawm(*, low_pass: float) -> Instrument:
    # Shawms and their cousins (suona, zurna, bombarde): loud, bright, hard-driven reeds
    return blown(
        falling_series(count=24, decibels_per_octave=2.0),
        attack=0.02,
        release=0.05,
        breath=0.015,
        low_pass=low_pass,
        drive=1.6,
    )


def _capped_reed(*, low_pass: float) -> Instrument:
    # A capped cylinder (the crumhorn): odd harmonics only, buzzy
    return blown(
        falling_series(count=20, decibels_per_octave=2.5, odd_only=True),
        attack=0.015,
        release=0.04,
        low_pass=low_pass,
        drive=1.0,
    )


def _duduk() -> Instrument:
    return blown(
        falling_series(count=10, decibels_per_octave=9.0),
        attack=0.07,
        release=0.12,
        breath=0.04,
        breath_low_pass=3000.0,
        low_pass=3500.0,
    )


_DOUBLE_REED_BUILDS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'oboe',
        'Oboe',
        Family.DOUBLE_REEDS,
        'Bb3',
        'A6',
        partial(_double_reed, OBOE_LEVELS, low_pass=7000.0),
    ),
    CatalogEntry(
        'oboe d amore',
        "Oboe d'amore",
        Family.DOUBLE_REEDS,
        'G#3',
        'C#6',
        partial(_double_reed, OBOE_LEVELS, low_pass=5500.0),
    ),
    CatalogEntry(
        'english horn',
        'English horn (cor anglais)',
        Family.DOUBLE_REEDS,
        'E3',
        'C6',
        partial(_double_reed, OBOE_LEVELS, low_pass=4500.0),
    ),
    CatalogEntry(
        'bass oboe',
        'Bass oboe',
        Family.DOUBLE_REEDS,
        'B2',
        'G5',
        partial(_double_reed, OBOE_LEVELS, low_pass=3800.0),
    ),
    CatalogEntry(
        'heckelphone',
        'Heckelphone',
        Family.DOUBLE_REEDS,
        'A2',
        'F5',
        partial(_double_reed, OBOE_LEVELS, low_pass=3500.0, drive=0.8),
    ),
    CatalogEntry(
        'bassoon',
        'Bassoon',
        Family.DOUBLE_REEDS,
        'Bb1',
        'E5',
        partial(_double_reed, BASSOON_LEVELS, low_pass=3500.0),
    ),
    CatalogEntry(
        'contrabassoon',
        'Contrabassoon',
        Family.DOUBLE_REEDS,
        'Bb0',
        'Bb3',
        partial(_double_reed, BASSOON_LEVELS, low_pass=2200.0),
    ),
    CatalogEntry(
        'sarrusophone',
        'Contrabass sarrusophone in C',
        Family.DOUBLE_REEDS,
        'Bb0',
        'G3',
        partial(_double_reed, BASSOON_LEVELS, low_pass=2500.0, drive=1.2),
    ),
    CatalogEntry(
        'soprano shawm',
        'Soprano shawm',
        Family.DOUBLE_REEDS,
        'D4',
        'B5',
        partial(_folk_shawm, low_pass=8000.0),
    ),
    CatalogEntry(
        'alto shawm',
        'Alto shawm',
        Family.DOUBLE_REEDS,
        'G3',
        'E5',
        partial(_folk_shawm, low_pass=6500.0),
    ),
    CatalogEntry(
        'tenor shawm',
        'Tenor shawm',
        Family.DOUBLE_REEDS,
        'C3',
        'A4',
        partial(_folk_shawm, low_pass=5000.0),
    ),
    CatalogEntry(
        'bass shawm',
        'Bass shawm',
        Family.DOUBLE_REEDS,
        'F2',
        'D4',
        partial(_folk_shawm, low_pass=4000.0),
    ),
    CatalogEntry(
        'suona', 'Suona', Family.DOUBLE_REEDS, 'D4', 'D6', partial(_folk_shawm, low_pass=8000.0)
    ),
    CatalogEntry(
        'zurna', 'Zurna', Family.DOUBLE_REEDS, 'C4', 'C6', partial(_folk_shawm, low_pass=8000.0)
    ),
    CatalogEntry(
        'bombarde',
        'Bombarde',
        Family.DOUBLE_REEDS,
        'Bb4',
        'C6',
        partial(_folk_shawm, low_pass=8000.0),
    ),
    CatalogEntry(
        'hichiriki',
        'Hichiriki',
        Family.DOUBLE_REEDS,
        'E4',
        'A5',
        partial(_folk_shawm, low_pass=6000.0),
    ),
    CatalogEntry(
        'piri', 'Piri', Family.DOUBLE_REEDS, 'Eb4', 'Bb5', partial(_folk_shawm, low_pass=6000.0)
    ),
    CatalogEntry(
        'soprano crumhorn',
        'Soprano crumhorn',
        Family.DOUBLE_REEDS,
        'C4',
        'D5',
        partial(_capped_reed, low_pass=5000.0),
    ),
    CatalogEntry(
        'alto crumhorn',
        'Alto crumhorn',
        Family.DOUBLE_REEDS,
        'F3',
        'G4',
        partial(_capped_reed, low_pass=4200.0),
    ),
    CatalogEntry(
        'tenor crumhorn',
        'Tenor crumhorn',
        Family.DOUBLE_REEDS,
        'C3',
        'D4',
        partial(_capped_reed, low_pass=3500.0),
    ),
    CatalogEntry(
        'bass crumhorn',
        'Bass crumhorn',
        Family.DOUBLE_REEDS,
        'F2',
        'G3',
        partial(_capped_reed, low_pass=2800.0),
    ),
    CatalogEntry(
        'rackett',
        'Rackett',
        Family.DOUBLE_REEDS,
        'C2',
        'C4',
        partial(_capped_reed, low_pass=2000.0),
    ),
    CatalogEntry('duduk', 'Duduk', Family.DOUBLE_REEDS, 'G3', 'C5', _duduk),
)

DOUBLE_REEDS: Final[tuple[CatalogEntry, ...]] = _DOUBLE_REED_BUILDS + DOUBLE_REED_SOUND_ALIKES
