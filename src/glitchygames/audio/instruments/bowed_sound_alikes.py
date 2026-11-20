"""Bowed strings' sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another size plays another span. A true alias, another name
for the same instrument, stays in ``aliases.py``. The family's builds are in ``bowed_strings.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family

BOWED_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 7's sound-alikes (the European and modern bowed strings), in the order of
    # plans/data/instrument-audit/batch-7.tsv: each a distinct instrument, verified by its source,
    # that no fetched source sets apart in sound from the entry it names (``sounds_like``)
    # Sound-alike of the violin (no fetched source sets it apart in sound):
    # https://renwks.com/products/psaltery-bow/psaltery-bow.htm (Renaissance Workshop Company, a
    # maker: "Strung in fine gauge steel music wire."; "A simple horsehair bow can be passed
    # between the pegs on each side to sound each string individually."; "There is no fretting:
    # each string is simply tuned to a different note."): a bowed steel string with nothing
    # sourced (no drone, body resonance or noise) to set it apart from a bowed violin string.
    # Range, from the same page, the maker's soprano, "the most popular size of psaltery": "It
    # has a fully chromatic two octave range f - f''.", which in Helmholtz's notation is F3 to
    # F5; its alto (Bb - bb') and tenor (F - f') are other sizes
    CatalogEntry(
        'bowed psaltery',
        'Bowed psaltery',
        Family.BOWED_STRINGS,
        'F3',
        'F5',
        sounds_like='violin',
    ),
    # Sound-alike of the viola (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Viola_pomposa ("the bottom four tuned conventionally of a
    # standard viola (C3-G3-D4-A4)" with "a high violin E string (E5)"; "a sound which is less
    # resonant than a viola, though still slightly more resonant than a violin"): a viola with one
    # more string, its tone between the viola's and the violin's. Range, from the same page: "has a
    # range from C3 to A6 (or even higher) with fingered notes": C3 is the lowest open string, A6
    # the compass the page states; "(or even higher)" and the harmonics "to C8" are not taken
    CatalogEntry(
        'viola pomposa',
        'Viola pomposa',
        Family.BOWED_STRINGS,
        'C3',
        'A6',
        sounds_like='viola',
    ),
)
