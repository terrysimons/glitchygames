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
    # Sound-alike of the contrabassoon (no sourced trait the engine can make audible):
    # https://en.wikipedia.org/wiki/Contraforte ("The contraforte uses a different and wider bore
    # than the contrabassoon to produce a distinct tone", cited there to Eppelsheim) and
    # Eppelsheim's maker page https://www.eppelsheim.com/en/instruments/contraforte/ ("wide bore
    # for a voluminous tone"). The wider bore is a sourced trait that the engine's double-reed
    # build cannot distinguish: with the contrabassoon's low pass, drive is the only lever, and
    # a lower one changes the crest factor by 1.5% and no sourced number gives it, so it builds
    # the contrabassoon's sound (conical, 422.112, like its parent). Range, from the maker's
    # page: "written range A1 - G 5, sounding A0 - G 4": the sounding range, an octave below
    # the written one
    CatalogEntry(
        'contraforte',
        'Contraforte',
        Family.DOUBLE_REEDS,
        'A0',
        'G4',
        sounds_like='contrabassoon',
    ),
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
    # --- Batch 11's folk and traditional shawms and oboes, in the order of
    # plans/data/instrument-audit/batch-11.tsv
    # Sound-alike of the duduk (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Balaban_(instrument) ("The balaban or balaman (Azerbaijani:
    # Balaban) is a double-reed pipe with cylindrical bore, about 35 centimetres (14 in) in
    # length, with eight finger holes and one thumb hole" and "The Azeri balaban, the Turkish
    # mey, and the Armenian duduk are almost identical, except for historical and geographical
    # differences."): the duduk's own cylindrical bore, with no trait of its own. Range, from the
    # Azerbaijan State Museum of Musical Culture, Balaban
    # (https://musicmuseum.az/en/index.php?id=90104): "The balaban's range goes from the "sol" of
    # the small octave to the "do" of the second octave." (the page's curly quotes are written
    # straight here): the small octave's sol is G3 and the second octave's do
    # is C5. The page's "The diapason can be expanded, depending upon the mastery of the
    # performer." is a top given to the player, so it is left out
    CatalogEntry(
        'balaban',
        'Balaban',
        Family.DOUBLE_REEDS,
        'G3',
        'C5',
        sounds_like='duduk',
    ),
)
