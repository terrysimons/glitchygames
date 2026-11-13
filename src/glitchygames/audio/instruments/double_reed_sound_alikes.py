"""Double reeds' sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another size plays another span. A true alias, another name
for the same instrument, stays in ``aliases.py``. The family's builds are in ``double_reeds.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family

DOUBLE_REED_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 11's sound-alikes (the orchestral, modern and early European double reeds), in
    # the order of plans/data/instrument-audit/batch-11.tsv: each a distinct instrument,
    # verified by its source, that no fetched source sets apart in sound from the entry it names
    # (``sounds_like``)
    # Sound-alike of the heckelphone (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Piccolo_heckelphone ("Following the basic principle of the
    # heckelphone, the piccolo heckelphone in F has an extremely wide bore with large tone
    # holes."): the heckelphone's own wide bore, with no trait of its own. Range, from the same
    # page: "A transposing instrument pitched in F, a perfect fourth above the oboe, its written
    # range is from B3 to E6" (cited there to Grove): the sounding notes, a perfect fourth above
    # the written B3 and E6, are E4 and A6
    CatalogEntry(
        'piccolo heckelphone',
        'Piccolo heckelphone in F',
        Family.DOUBLE_REEDS,
        'E4',
        'A6',
        sounds_like='heckelphone',
    ),
)
