"""Clarinets' sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another size plays another span. A true alias, another name
for the same instrument, stays in ``aliases.py``. The family's builds are in ``clarinets.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family

CLARINET_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 14's clarinets, in the order of plans/data/instrument-audit/batch-14.tsv: each a
    # distinct instrument, verified by its source, that no fetched source sets apart in sound from
    # the clarinet entry it names (``sounds_like``).
    # Sound-alike of the clarinet (the B-flat clarinet), unchanged: the Vienna Symphonic
    # Library's academy page Clarinet in Bb (https://www.vsl.co.at/academy/woodwinds/clarinet)
    # describes the clarinets in C, B-flat and A together: "C clarinet: brighter, colder and
    # harder, more "pert" than the other two clarinets." Brighter, colder and harder are colour
    # words, no cited trait the build makes. Its reed and bore, for every clarinet: "Beak-shaped
    # mouthpiece made of ebonite or cocus wood with a single reed", "Mainly cylindrical,
    # barrel-shaped bulge below the mouthpiece (barrel)" and "when sound is produced only the odd
    # harmonics speak": a single reed on a cylindrical bore, the clarinet's build. Parent: the
    # page relates it to "the other two clarinets", the B-flat and the A; of those the clarinet
    # (D3) is nearest its lowest note E3. Range, from the same page: "On all clarinets the
    # written compass ranges from E3 - C7." and "On the C clarinet the sound is as written.", so
    # the range sounds as given, E3-C7
    CatalogEntry(
        'c clarinet',
        'C clarinet',
        Family.CLARINETS,
        'E3',
        'C7',
        sounds_like='clarinet',
    ),
)
