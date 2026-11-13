"""Saxophones' sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another size plays another span. A true alias, another name
for the same instrument, stays in ``aliases.py``. The family's builds are in ``saxophones.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family

SAXOPHONE_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 19's saxophones, in the order of plans/data/instrument-audit/batch-19.tsv: each a
    # distinct instrument, verified by its source, that no fetched source sets apart in sound from
    # the saxophone entry it names (``sounds_like``). Flats are written as b in these comments (the
    # sources' flat and sharp signs are not ASCII), and each quote writes the maker's en dash as a
    # hyphen.
    # Sound-alike of the sopranino saxophone, unchanged. Sound source: the Soprillo page
    # (https://en.wikipedia.org/wiki/Soprillo): "is the highest pitched and smallest saxophone."
    # and "The soprillo was developed as a piccolo extension to the saxophone family in the late
    # 1990s by the German instrument maker Benedikt Eppelsheim". Its reed, from the maker's page
    # (https://www.eppelsheim.com/en/instruments/soprillo/): "uses Eb , Ab or German style Bb
    # clarinet reeds or sopranino sax reeds", a single reed. Its bore: the Saxophone page's lead
    # (https://en.wikipedia.org/wiki/Saxophone): "is a type of single-reed woodwind instrument with
    # a conical body": a single reed on a conical bore, the saxophones' build. Size (a straight
    # body, a non-removable mouthpiece) and the extreme embouchure it asks of a player are no trait
    # the build makes. Parent: the page relates it to the soprano by pitch and shape, which does
    # not count, so the catalog saxophone whose lowest note is nearest its lowest note Ab4: the
    # sopranino saxophone (Db4) is 7 semitones below, the soprano saxophone (Ab3) 12. Range, from
    # the maker's page description: "Soprillo Bb piccolo saxophone written range Bb 3" and "Eb 6,
    # sounding Ab4-Db 7": sounding Ab4 to Db7. The Soprillo page's transposition agrees ("The
    # soprillo in Bb sounds a minor seventh higher than written."): written Bb3 up a minor seventh
    # is Ab4, written Eb6 up a minor seventh is Db7.
    CatalogEntry(
        'soprillo saxophone',
        'Soprillo saxophone',
        Family.SAXOPHONES,
        'Ab4',
        'Db7',
        sounds_like='sopranino saxophone',
    ),
    # Sound-alike of the contrabass saxophone, unchanged. Sound source: the Tubax page
    # (https://en.wikipedia.org/wiki/Tubax): "The tubax is a modified contrabass saxophone
    # developed in 1999 by the German instrument maker Benedikt Eppelsheim." and "The first size of
    # tubax to be developed was the Eb (contrabass) tubax, introduced at the Musikmesse Frankfurt
    # in 1999 and intended as a more practical alternative to the contrabass saxophone." Reed and
    # bore: "allowing the use of a smaller mouthpiece (baritone or bass size, instead of a larger
    # contrabass mouthpiece)" and "They are built with a narrower conical bore, somewhere between a
    # regular saxophone and a contrabass sarrusophone": a single-reed saxophone mouthpiece on a
    # conical bore. The maker's page (https://www.eppelsheim.com/en/instruments/tubax-eb/):
    # "baritone saxophone mouthpiece" and "narrow bore for less air consumption and a reasonable
    # overall height (114 cm = 45 inches) by a completely new body design": the bore's stated
    # effects are on the air and the height, not on the sound. The two lines that state a sound
    # ("a more focused and compact timbre", "reedier") are uncited and colour words, so no trait.
    # Parent: the page relates the whole instrument to the contrabass saxophone ("derived from
    # the contrabass saxophone"), whose lowest note Db1 is also this one's. Range, from the
    # maker's page description: "Tubax Eb contrabass saxophone range Bb 3-F#6, sounding Db1-A 3":
    # sounding Db1 to A3. Its altissimo key ("sounding F 4") is an extension beyond the stated
    # range, not taken.
    CatalogEntry(
        'tubax in eb',
        'Tubax in E♭',
        Family.SAXOPHONES,
        'Db1',
        'A3',
        sounds_like='contrabass saxophone',
    ),
)
