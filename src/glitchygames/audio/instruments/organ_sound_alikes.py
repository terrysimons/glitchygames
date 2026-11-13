"""Organs' sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another size plays another span. A true alias, another name
for the same instrument, stays in ``aliases.py``. A sound-alike stop whose source gives it
another footage than its parent carries it as ``sound_changes``, its only change. The family's
builds are in ``organs.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family

ORGAN_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 13's organ stops, in the order of plans/data/instrument-audit/batch-13.tsv: each a
    # distinct stop, verified by its source, that no fetched source sets apart in sound from the
    # organ entry it names (``sounds_like``). A stop's range is its keys at 8' pitch. The manual
    # compass, for the stops that play from a manual: the Pipe organ page
    # (https://en.wikipedia.org/wiki/Pipe_organ, its Keyboards paragraph, cited there to the
    # American Guild of Organists' Pipe Organ Guide, in Helmholtz notation): "Most current
    # specifications call for two or more manuals with sixty-one notes (five octaves, from C to
    # c⁗)"; the cited guide (archived,
    # https://web.archive.org/web/20070927154656/http://www.agohq.org/guide/pages/pages_5_5/frameset01.html):
    # "Most American organs have 61 notes on the manuals-to C above high C"; and the AGO's
    # Standard Console Guidelines as Organ Supply Industries reproduces them
    # (https://www.organsupply.com/assets/Brochures/Console-Tri-Fold.pdf): "Compass: CC to c4, 61
    # notes." C is C2 and c⁗ is C7, 61 keys
    # Sound-alike of the stopped diapason, an octave lower (its footage, its only change): the
    # Encyclopedia of Organ Stops (http://www.organstops.org/b/Bourdon.html): "A 16' stopped
    # wooden flute of large scale.", "It is possibly the single most common 16' pedal stop." and
    # "It is similar to, and occasionally synonymous with, the Gedeckt and the Stopped Diapason."
    # Audsley, The Organ of the Twentieth Century (1919,
    # https://archive.org/download/organoftwentieth00audsuoft/organoftwentieth00audsuoft_djvu.txt):
    # "Covered pipes cannot give the uneven upper partial tones" and "The most important covered
    # wood stops are the STOPPED DIAPASON, BOURDON, ...": the stopped diapason's missing even
    # harmonics. Footage: 16, the Encyclopedia's ("A 16' stopped wooden flute"), so
    # sound_changes={'footage': 16.0}. Range: the stop's division is the pedal (Audsley,
    # Organ-Stops and Their Artistic Registration, 1921,
    # https://archive.org/download/cu31924086010331/cu31924086010331_djvu.txt: "The Bourdon, 16
    # ft., most frequently appears, in English and American instruments of moderate dimensions, in
    # the Pedal Organ"). The AGO's Standard Console Guidelines
    # (https://www.organsupply.com/assets/Brochures/Console-Tri-Fold.pdf), under Pedalboard:
    # "Compass: 32 notes, CCC to G"; the AGO's Pipe Organ Guide (archived, above): "low C is also
    # the lowest written note" and "others have 32-to G above middle C". So the keys are C2 (low C)
    # to G4 (G above middle C), 32 keys, sounding C1-G3 at 16'
    CatalogEntry(
        'bourdon',
        "Bourdon 16'",
        Family.ORGANS,
        'C2',
        'G4',
        sounds_like='stopped diapason',
        sound_changes={'footage': 16.0},
    ),
    # Sound-alike of the organ clarinet (the same half-length cylindrical resonator): the
    # Encyclopedia of Organ Stops (http://www.organstops.org/k/Krummhorn.html): "the organ stop in
    # its most familiar form has a tone resembling that of the Clarinet" and "It was usually made
    # with narrow cylindrical half-length resonators." Audsley, Organ-Stops and Their Artistic
    # Registration (1921, https://archive.org/download/cu31924086010331/cu31924086010331_djvu.txt),
    # CROMORNE: "Ger., Krummhorn. — The name used by French and German organ-builders to
    # designate a lingual stop, the tone of which somewhat resembles that of the Clarinet, but
    # with a smoother and mournful character." and "It is commonly of 8 ft. pitch." Range: the
    # manual, C2-C7, at 8'
    CatalogEntry(
        'organ krummhorn',
        "Krummhorn 8'",
        Family.ORGANS,
        'C2',
        'C7',
        sounds_like='organ clarinet',
    ),
    # Sound-alike of pipe organ reed (a reed with a full-length conical resonator, the trumpet's
    # form): Audsley, Organ-Stops and Their Artistic Registration (1921,
    # https://archive.org/download/cu31924086010331/cu31924086010331_djvu.txt), OBOE: "The
    # resonators of the unimitative Oboe, 8 ft., are approximately of the standard speaking
    # lengths; and are in the form of slender tapered tubes surmounted by long inverted conical
    # bells" and "A lingual stop, of 8 ft. pitch, which belongs to the manual department of the
    # Organ." Its softness is a loudness and its bell no buildable trait. Range: the manual,
    # C2-C7, at 8'
    CatalogEntry(
        'organ oboe',
        "Oboe 8'",
        Family.ORGANS,
        'C2',
        'C7',
        sounds_like='pipe organ reed',
    ),
    # Sound-alike of pipe organ reed (a chorus reed of the trumpet class): the Encyclopedia of
    # Organ Stops (http://www.organstops.org/t/Tuba.html): "The Tuba is the most powerful organ
    # stop.", "It is constructed in the manner of a large-scale Trumpet, though often with closed
    # shallots." and "It is most commonly found at 8' pitch." Audsley, Organ-Stops and Their
    # Artistic Registration (1921,
    # https://archive.org/download/cu31924086010331/cu31924086010331_djvu.txt), TUBA: "The pipes of
    # the Tuba are, like those of the Trumpet (Fig. 34) of inverted conical form, of large scale"
    # and "its most desirable place is in the manual division containing the principal solo
    # stops". Its power is a loudness and its scale a scale. Range: the manual, C2-C7, at 8'
    CatalogEntry(
        'organ tuba',
        "Tuba 8'",
        Family.ORGANS,
        'C2',
        'C7',
        sounds_like='pipe organ reed',
    ),
    # Sound-alike of pipe organ reed (a chorus reed): the Encyclopedia of Organ Stops
    # (http://www.organstops.org/p/PostHorn.html), quoting Maclean on the English Post Horn:
    # "represent the extreme limit of brassy, strident Reed tone"; "Strony calls the English
    # Post Horn “the king of theatre organ chorus reeds”" and "reports that it typically appears
    # at 8' pitch". No harmonic content is stated, and its loudness is no trait. Range: the
    # manual, C2-C7, at 8'
    CatalogEntry(
        'posthorn',
        "Post horn 8'",
        Family.ORGANS,
        'C2',
        'C7',
        sounds_like='pipe organ reed',
    ),
    # Sound-alike of pipe organ string (a string stop): Audsley, Organ-Stops and Their Artistic
    # Registration (1921, https://archive.org/download/cu31924086010331/cu31924086010331_djvu.txt),
    # SALICIONAL: "The names given to open labial stops formed of cylindrical metal pipes of
    # medium or small scales, belonging to the Viol family." The Encyclopedia of Organ Stops
    # (http://www.organstops.org/s/Salicional.html): "Now one of the most common string stops" and
    # "it is most often found at 8' pitch". Range: the manual, C2-C7, at 8' (Audsley: "the
    # Salicional, 8 ft., occupies its usual place in the Swell")
    CatalogEntry(
        'salicional',
        "Salicional 8'",
        Family.ORGANS,
        'C2',
        'C7',
        sounds_like='pipe organ string',
    ),
    # Sound-alike of pipe organ string (its usual form, one string rank tuned sharp, beats only
    # against another stop drawn with it, a registration): the Encyclopedia of Organ Stops
    # (http://www.organstops.org/v/VoixCeleste.html): "The ubiquitous Voix Céleste is typically a
    # single rank of pipes yielding a mild string tone, found in Swell divisions and intended for
    # use with a Salicional or Viola da Gamba." Audsley, Organ-Stops and Their Artistic
    # Registration (1921, https://archive.org/download/cu31924086010331/cu31924086010331_djvu.txt),
    # VOIX CELESTE: "In the large majority of examples, the stop is of one rank only, of either
    # string-toned or pure organ-toned metal pipes, tuned a few beats sharp" and "an open labial
    # stop, of 8 ft. pitch". Range: the manual, C2-C7, at 8'
    CatalogEntry(
        'voix celeste',
        "Voix céleste 8'",
        Family.ORGANS,
        'C2',
        'C7',
        sounds_like='pipe organ string',
    ),
)
