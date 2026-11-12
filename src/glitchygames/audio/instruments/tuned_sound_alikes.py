"""Tuned percussion's sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another size plays another span. A true alias, another name
for the same instrument, stays in ``aliases.py``. The family's builds are in ``percussion.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family

TUNED_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 5's bars, plaques, tubes and stones, in the order of
    # plans/data/instrument-audit/batch-5.tsv: each a distinct instrument, verified by its
    # source, that no fetched source sets apart in sound from the entry it names. Each builds
    # that entry's instrument (``sounds_like``); the sheet's notes give each row's full quotes.
    # Sound-alike of the glockenspiel (no fetched source sets it apart in sound):
    # https://www.guitarcenter.com/Lyons/Glockenspiel-Regular-Wide-Bar-Diatonic.gc
    # ("The note range for the Alto Wide Bar Glockenspiel is C5 to A6."; "Hand lathed and hand
    # tuned aluminum wide body tone bars ... combine a bright sound with steady overtones"):
    # aluminum bars struck with hard mallets, the glockenspiel at another register. Range C5-A6
    # from the listing
    CatalogEntry(
        'alto glockenspiel',
        'Alto glockenspiel (Orff)',
        Family.TUNED_PERCUSSION,
        'C5',
        'A6',
        sounds_like='glockenspiel',
    ),
    # Sound-alike of the glockenspiel (no fetched source sets it apart in sound):
    # https://www.guitarcenter.com/Lyons/Metallophone-Regular-Diatonic.gc
    # ("The note range for the Alto Metallophone is C4 to A5 and includes Add-on bars F#4, Bb4,
    # and F#5."; "Hand-lathed and hand-tuned aluminum tone bars combine a bright sound with steady
    # overtones."; "a chambered wood box enhancing tone"): the Lyons text gives its glockenspiels
    # the same words, so the glockenspiel is the nearest. Range C4-A5 from the listing
    CatalogEntry(
        'alto metallophone',
        'Alto metallophone (Orff)',
        Family.TUNED_PERCUSSION,
        'C4',
        'A5',
        sounds_like='glockenspiel',
    ),
    # Sound-alike of the xylophone (no fetched source sets it apart in sound):
    # https://GuitarCenter.com/Open-Box/Lyons/Xylophone-Regular-Diatonic.gc ("16-note Stamped Bars
    # C4 to A5 (Alto)"; "Aged moisture controlled wood bars") and
    # https://en.wikipedia.org/wiki/Xylophone ("The alto ranges are written from middle C to A an
    # octave higher and sound as written."): wooden bars, the xylophone's sound. Range C4-A5
    # from the listing
    CatalogEntry(
        'alto xylophone',
        'Alto xylophone (Orff)',
        Family.TUNED_PERCUSSION,
        'C4',
        'A5',
        sounds_like='xylophone',
    ),
    # Sound-alike of the glockenspiel (no fetched source sets it apart in sound):
    # https://www.guitarcenter.com/Lyons/Metallophone-Regular-Diatonic.gc
    # ("The note range for the Bass Metallophone is C3 to A4 and includes Add-on bars F#3, Bb3,
    # and F#4."; "Hand-lathed and hand-tuned aluminum tone bars combine a bright sound with steady
    # overtones."; "a chambered wood box enhancing tone"): the Lyons text gives its glockenspiels
    # the same words, so the glockenspiel is the nearest. Range C3-A4 from the listing
    CatalogEntry(
        'bass metallophone',
        'Bass metallophone (Orff)',
        Family.TUNED_PERCUSSION,
        'C3',
        'A4',
        sounds_like='glockenspiel',
    ),
    # Sound-alike of the xylophone (no fetched source sets it apart in sound):
    # https://www.guitarcenter.com/Open-Box/Lyons/Xylophone-Regular-Diatonic-Level-1-Bass-K64633004003000.gc
    # ("16-note Stamped Bars C3 to A4 (Bass)"; "Aged moisture controlled wood bars"; "an
    # all-wood chamber, wood tone bars and metal resonators") and
    # https://en.wikipedia.org/wiki/Xylophone ("The bass xylophone ranges are written from middle C
    # to A an octave higher but sound one octave lower than written"). Range C3-A4 from the listing
    CatalogEntry(
        'bass xylophone',
        'Bass xylophone (Orff)',
        Family.TUNED_PERCUSSION,
        'C3',
        'A4',
        sounds_like='xylophone',
    ),
    # Sound-alike of the gangsa (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Gamelan_gong_kebyar ("These instruments are the highest sounding
    # in the kebyar ensemble, with its highest note being around C7. It has ten keys, and a range of
    # two octaves, and is played with a wooden hammer."): the pemade's ten keys, resonators and
    # paired tuning an octave higher. Range C5-C7 derived from that (approximate: "around C7")
    CatalogEntry(
        'kantilan',
        'Balinese kantilan',
        Family.TUNED_PERCUSSION,
        'C5',
        'C7',
        sounds_like='gangsa',
    ),
    # Sound-alike of the glockenspiel (no fetched source sets it apart in sound):
    # https://www.guitarcenter.com/Lyons/Glockenspiel-Regular-Wide-Bar-Diatonic.gc
    # ("The note range for the Soprano Wide Bar Glockenspiel is C6 to A7."; "Hand lathed and hand
    # tuned aluminum wide body tone bars ... combine a bright sound with steady overtones"):
    # aluminum bars, the glockenspiel at another register. Range C6-A7 from the listing
    CatalogEntry(
        'soprano glockenspiel',
        'Soprano glockenspiel (Orff)',
        Family.TUNED_PERCUSSION,
        'C6',
        'A7',
        sounds_like='glockenspiel',
    ),
    # Sound-alike of the glockenspiel (no fetched source sets it apart in sound):
    # https://www.guitarcenter.com/Lyons/Metallophone-Regular-Diatonic.gc
    # ("The note range for the Soprano Metallophone is C5 to A6 and includes Add-on bars F#5, Bb5,
    # and F#6."; "Hand-lathed and hand-tuned aluminum tone bars combine a bright sound with steady
    # overtones."): the Lyons text gives its glockenspiels the same words, so the glockenspiel is
    # the nearest. Range C5-A6 from the listing
    CatalogEntry(
        'soprano metallophone',
        'Soprano metallophone (Orff)',
        Family.TUNED_PERCUSSION,
        'C5',
        'A6',
        sounds_like='glockenspiel',
    ),
    # Sound-alike of the xylophone (no fetched source sets it apart in sound):
    # https://www.guitarcenter.com/Lyons/Xylophone-Regular-Diatonic.gc ("16-note Stamped Bars C5 to
    # A6 (Soprano)"; "Aged moisture controlled wood bars") and
    # https://en.wikipedia.org/wiki/Xylophone ("The soprano ranges are written from middle C to A an
    # octave higher but sound one octave higher than written"). Range C5-A6 from the listing
    CatalogEntry(
        'soprano xylophone',
        'Soprano xylophone (Orff)',
        Family.TUNED_PERCUSSION,
        'C5',
        'A6',
        sounds_like='xylophone',
    ),
    # Sound-alike of the glockenspiel (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tubaphone ("A tubaphone is a type of metallophone constructed
    # from a series of metal tubes arranged in a keyboard configuration. The tubes are similar in
    # length to that of a xylophone, and sound vaguely like a glockenspiel."; infobox range
    # "C6-C8"): the page says it sounds like a glockenspiel and gives no tube trait to build it
    # apart. Range C6-C8 from the infobox
    CatalogEntry(
        'tubaphone',
        'Tubaphone',
        Family.TUNED_PERCUSSION,
        'C6',
        'C8',
        sounds_like='glockenspiel',
    ),
    # Sound-alike of the gangsa (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ugal ("It is a bronze metallophone played one handed with a
    # small hammer"; "There are usually ten keys, giving a maximum range spanning about two
    # octaves. Like the gangsa and gendèr, they are suspended over tuned bamboo resonators."; "Its
    # notes are an octave lower than those of the gangsa pemadé."): the pemade's keys and
    # resonators an octave lower. Range C3-C5 derived from the pemade's C4-C6 (approximate,
    # nominal)
    CatalogEntry(
        'ugal',
        'Balinese ugal',
        Family.TUNED_PERCUSSION,
        'C3',
        'C5',
        sounds_like='gangsa',
    ),
)
