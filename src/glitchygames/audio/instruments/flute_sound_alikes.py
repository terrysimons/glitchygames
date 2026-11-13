"""Flutes' sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another size plays another span. A true alias, another name
for the same instrument, stays in ``aliases.py``. The family's builds are in ``flutes.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family

FLUTE_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 9's sound-alikes (the European, orchestral and modern flutes, whistles and
    # calls), in the order of build/batch-9-half-a.tsv: each a distinct instrument, verified by
    # its source, that no fetched source sets apart in sound from the entry it names
    # (``sounds_like``)
    # Sound-alike of the soprano recorder (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Csakan ("A type of duct flute, the csakan was originally a
    # recorder crafted in the shape of a walking stick with a mouthpiece in the handle"; "Modern
    # manufacturers refer to it as "the Romantic recorder"."): a recorder with nothing sourced
    # (no bore, material or duct) to set it apart; the soprano recorder (C5-D7) is the size
    # nearest its register. Range, from the same page: "Notated: (B3)C4-G6(B6) Sounding:
    # (G4)A-flat4-E-flat7(G7)" and "The csakan is a transposing instrument in A-flat": the
    # sounding notes, a minor sixth above the written C4 and G6, are Ab4 and Eb7; the
    # parenthesised notes are the extended range, extremes the instrument does not play
    CatalogEntry(
        'csakan',
        'Csakan',
        Family.FLUTES,
        'Ab4',
        'Eb7',
        sounds_like='soprano recorder',
    ),
    # Sound-alike of the contrabass recorder (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Sub-contrabass_recorder ("The sub-contrabass recorder is a
    # member of the recorder family with a low note of FF (or F1 in SPN)."; "It is manufactured
    # with a square or rectangular cross-sectional design, which was first patented in 1975 by
    # Joachim and Herbert Paetzold."): the square section is construction with no sound trait
    # named, so it builds the contrabass recorder (F2-G4), the size nearest in register. Range,
    # from Paetzold by Kunath, the maker's Subkontrabass manual
    # (https://kunath.com/media/bf/31/d8/1726607706/PbK-Subkontrabass-Handbuch.pdf: "Der
    # Subkontrabass (Kontrasubbass) mit dem Grundton F1 klingt eine Oktave tiefer als notiert.
    # Tonumfang klingend:"; "Er ist über 2 Oktaven chromatisch spielbar."): the sounding
    # range is printed on a bass staff, F1 (the stated Grundton) to G3, read from the PDF page
    CatalogEntry(
        'subcontrabass recorder',
        'Subcontrabass recorder in F',
        Family.FLUTES,
        'F1',
        'G3',
        sounds_like='contrabass recorder',
    ),
)
