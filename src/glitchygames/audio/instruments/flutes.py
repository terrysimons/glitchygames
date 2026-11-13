"""Flutes: the edge-blown aerophones, from the concert flute and recorders to panpipes and ocarinas.

The sound is made by a breath split on an edge: Hornbostel-Sachs 421 (edge-blown flutes: the
transverse, end-blown, duct and vessel flutes and the panpipes). The spec's boundary calls put
duck calls, signal whistles and the hydraulophone here too. The family's sound-alikes, listed
instruments that share another entry's build, are in ``flute_sound_alikes.py``. The double reeds
are in the sibling module ``double_reeds.py``, the bagpipes in ``bagpipes.py``, the clarinets in
``clarinets.py``, the saxophones in ``winds.py`` and the free reeds in ``free_reeds.py``.

Ranges are sounding pitch, after the standard orchestration ranges (Adler, *The Study of
Orchestration*; Vienna Symphonic Library's instrument pages); folk instruments' are typical of the
common keys. Timbres follow the instruments' acoustics: a flute is nearly pure with breath.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.flute_sound_alikes import FLUTE_SOUND_ALIKES
from glitchygames.audio.instruments.timbres import blown, falling_series

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument


def _flute(  # ruff: ignore[too-many-arguments] - the flute family's traits
    *,
    slope: float,
    breath: float,
    breath_low_pass: float = 5000.0,
    attack: float = 0.05,
    even_level: float = 1.0,
    chorus_cents: float = 0.0,
) -> Instrument:
    return blown(
        falling_series(count=10, decibels_per_octave=slope, even_level=even_level),
        attack=attack,
        release=0.08,
        breath=breath,
        breath_low_pass=breath_low_pass,
        chorus_cents=chorus_cents,
    )


METAL_FLUTE = partial(_flute, slope=13.0, breath=0.04, breath_low_pass=7000.0)
WOODEN_FLUTE = partial(_flute, slope=17.0, breath=0.07, breath_low_pass=4500.0, attack=0.06)
RECORDER = partial(_flute, slope=16.0, breath=0.025, attack=0.03, even_level=0.6)
WHISTLE = partial(_flute, slope=14.0, breath=0.045, attack=0.015)
END_BLOWN = partial(_flute, slope=15.0, breath=0.14, breath_low_pass=5000.0, attack=0.08)
VESSEL = partial(_flute, slope=26.0, breath=0.02, attack=0.03)

_FLUTE_BUILDS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry('piccolo', 'Piccolo', Family.FLUTES, 'D5', 'C8', METAL_FLUTE),
    CatalogEntry('flute', 'Concert flute (metal)', Family.FLUTES, 'C4', 'D7', METAL_FLUTE),
    CatalogEntry('alto flute', 'Alto flute in G', Family.FLUTES, 'G3', 'G6', METAL_FLUTE),
    CatalogEntry('bass flute', 'Bass flute', Family.FLUTES, 'C3', 'C6', METAL_FLUTE),
    CatalogEntry('contra alto flute', 'Contra-alto flute', Family.FLUTES, 'G2', 'G5', METAL_FLUTE),
    CatalogEntry('contrabass flute', 'Contrabass flute', Family.FLUTES, 'C2', 'C5', METAL_FLUTE),
    CatalogEntry(
        'wooden flute', 'Wooden flute (simple-system)', Family.FLUTES, 'D4', 'D6', WOODEN_FLUTE
    ),
    CatalogEntry(
        'wooden concert flute', 'Wooden concert flute', Family.FLUTES, 'C4', 'C7', WOODEN_FLUTE
    ),
    CatalogEntry(
        'baroque flute', 'Baroque flute (traverso)', Family.FLUTES, 'D4', 'E6', WOODEN_FLUTE
    ),
    CatalogEntry('fife', 'Fife', Family.FLUTES, 'D5', 'D7', METAL_FLUTE),
    CatalogEntry('tin whistle', 'Tin whistle in D', Family.FLUTES, 'D5', 'D7', WHISTLE),
    CatalogEntry('low whistle', 'Low whistle in D', Family.FLUTES, 'D4', 'D6', WHISTLE),
    CatalogEntry('sopranino recorder', 'Sopranino recorder', Family.FLUTES, 'F5', 'G7', RECORDER),
    CatalogEntry('soprano recorder', 'Soprano recorder', Family.FLUTES, 'C5', 'D7', RECORDER),
    CatalogEntry('alto recorder', 'Alto recorder', Family.FLUTES, 'F4', 'G6', RECORDER),
    CatalogEntry('tenor recorder', 'Tenor recorder', Family.FLUTES, 'C4', 'D6', RECORDER),
    CatalogEntry('bass recorder', 'Bass recorder', Family.FLUTES, 'F3', 'G5', RECORDER),
    CatalogEntry('great bass recorder', 'Great bass recorder', Family.FLUTES, 'C3', 'D5', RECORDER),
    CatalogEntry('contrabass recorder', 'Contrabass recorder', Family.FLUTES, 'F2', 'G4', RECORDER),
    CatalogEntry('pan flute', 'Pan flute', Family.FLUTES, 'C4', 'C7', END_BLOWN),
    CatalogEntry('shakuhachi', 'Shakuhachi', Family.FLUTES, 'D4', 'D6', END_BLOWN),
    CatalogEntry('bansuri', 'Bansuri', Family.FLUTES, 'E4', 'E6', WOODEN_FLUTE),
    CatalogEntry('dizi', 'Dizi', Family.FLUTES, 'A4', 'C7', METAL_FLUTE),
    CatalogEntry('xiao', 'Xiao', Family.FLUTES, 'D4', 'D6', END_BLOWN),
    CatalogEntry('quena', 'Quena', Family.FLUTES, 'G4', 'A6', END_BLOWN),
    CatalogEntry('ney', 'Ney', Family.FLUTES, 'C4', 'C6', END_BLOWN),
    CatalogEntry('kaval', 'Kaval', Family.FLUTES, 'D4', 'D6', END_BLOWN),
    CatalogEntry(
        'native american flute', 'Native American flute', Family.FLUTES, 'F#4', 'F#5', WOODEN_FLUTE
    ),
    CatalogEntry('ocarina', 'Ocarina (alto C)', Family.FLUTES, 'C5', 'F6', VESSEL),
    CatalogEntry('bass ocarina', 'Bass ocarina', Family.FLUTES, 'C3', 'F4', VESSEL),
)


FLUTES: Final[tuple[CatalogEntry, ...]] = _FLUTE_BUILDS + FLUTE_SOUND_ALIKES
