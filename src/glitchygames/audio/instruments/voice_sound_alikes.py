"""Voices' and choirs' sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another voice type sings another span. A true alias,
another name for the same instrument, stays in ``aliases.py``. The families' builds are in
``voices.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family

VOICE_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 8's sound-alikes, in the order of plans/data/instrument-audit/batch-8.tsv
    # Sound-alike of the bass (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bass_(voice_type) ('basso buffo ("comical bass" light, agile
    # bass or bass-baritone range)'; 'Buffo, literally "funny", basses are lyrical roles that
    # demand from their practitioners a solid coloratura technique, a capacity for patter singing
    # and ripe tonal qualities'): a kind of bass whose sourced words (light, agile, patter) are
    # weight and agility, not a formant row of its own. Range, from
    # https://en.wikipedia.org/wiki/Fach (Bass Fächer, "Spielbass / Bassbuffo / Lyric buffo"):
    # "Range: From the E half an octave below low C (E2) to the F above middle C (F4)", which is
    # E2 to F4 (the heading's "half an octave" is loose; the page fixes the note as E2)
    CatalogEntry(
        'basso buffo ah',
        'Basso buffo (ah)',
        Family.VOICES,
        'E2',
        'F4',
        sounds_like='bass ah',
    ),
)
CHOIR_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = ()
