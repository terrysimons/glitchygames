"""Brass's sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another size plays another span. A true alias, another name
for the same instrument, stays in ``aliases.py``. The family's builds are in ``brass.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family

BRASS_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 10's sound-alikes (the valved, slide, keyed and fingered brass), in the order of
    # plans/data/instrument-audit/batch-10.tsv: each a distinct instrument, verified by its
    # source, that no fetched source sets apart in sound from the entry it names
    # (``sounds_like``)
    # Sound-alike of the wagner tuba (the tenor, HORN), no fetched source sets it apart in sound:
    # https://en.wikipedia.org/wiki/Wagner_tuba ("The Wagner tuba nominally exists in two sizes,
    # tenor in B-flat and bass in F, with ranges comparable to those of horns in the same pitches
    # while being less adept at the highest notes."; "Wagner's desired aural effect was obtained
    # by a conical bore, similar to a horn, and the use of the horn mouthpiece"): the page
    # describes both sizes alike, so the bass is a size of the tenor, with no bore or mouthpiece
    # of its own sourced. Range, from the Vienna Symphonic Library's Wagner tuba - Range page
    # (archived 3 August 2021):
    # https://web.archive.org/web/20210803165145/https://www.vsl.co.at/en/Wagner_tuba/Range
    # ("The range of the bass Wagner tuba in F is Eb1 - F5 (no transposition)."), the sounding
    # range, since its Notation page (archived,
    # https://web.archive.org/web/20210803181608/https://www.vsl.co.at/en/Wagner_tuba/Notation)
    # gives the bass "Sounds a fifth lower than written."
    CatalogEntry(
        'bass wagner tuba',
        'Bass Wagner tuba in F',
        Family.BRASS,
        'Eb1',
        'F5',
        sounds_like='wagner tuba',
    ),
    # Sound-alike of the trumpet (the B-flat trumpet, TRUMPET), no fetched source sets it apart
    # in sound: https://en.wikipedia.org/wiki/Soprano_trombone ("As the bore, bell and
    # mouthpiece are similar to the B-flat trumpet, it tends to be played by trumpet players
    # rather than trombonists."; "It usually takes a trumpet mouthpiece"): the slide chooses the
    # notes, not the sound, and the page gives it no trait of its own. Range, from the same
    # page: "The range of the B-flat soprano trombone is similar to the B-flat trumpet, E3 to
    # C6.", its range score captioned "The (sounding) range of the B-flat soprano trombone."
    CatalogEntry(
        'soprano trombone',
        'Soprano trombone in B♭',
        Family.BRASS,
        'E3',
        'C6',
        sounds_like='trumpet',
    ),
)
