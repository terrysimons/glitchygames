"""Plucked strings' sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another size plays another span. A true alias, another name
for the same instrument, stays in ``aliases.py``. The family's builds are in
``plucked_strings.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family

PLUCKED_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 4's sound-alikes (necked lutes), in the order of
    # plans/data/instrument-audit/batch-4.tsv: each a distinct instrument, verified by its source,
    # that no fetched source sets apart in sound from the entry it names. Each builds that entry's
    # instrument (``sounds_like``); the sheet's notes give each row's full quotes and why it
    # sounds like its parent. A later source giving a trait that sets one apart makes it a changed
    # sound-alike (``sound_changes``) or its own build.
    # Sound-alike of the acoustic bass guitar (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ukulele (the size chart: "16-18 | E2-B4 (C♯5) | E2 A2 D3
    # G3"; "E2-A2-D3-G3, for Ohana type metal-string basses"): a metal-string bass ukulele tuned
    # like a bass guitar, no fetched source sets it apart in sound. Range E2-B4 from the chart
    CatalogEntry(
        'bass ukulele',
        'Bass ukulele (metal-string)',
        Family.PLUCKED_STRINGS,
        'E2',
        'B4',
        sounds_like='acoustic bass guitar',
    ),
    # Sound-alike of the acoustic bass guitar (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ukulele (the size chart: "Contrabass | U-Bass, Rumbler | 32
    # in (81 cm) | 21 in (53 cm) | 16 | E1-B3 | E1 A1 D2 G2"; "E1-A1-D2-G2 for U-Bass style
    # instruments (sometimes called contrabass)"): the page gives no string material or other
    # sound trait, so the acoustic bass guitar, in bass guitar tuning, is the nearest. Range
    # E1-B3 from the chart
    CatalogEntry(
        'contrabass ukulele',
        'Contrabass ukulele (U-Bass)',
        Family.PLUCKED_STRINGS,
        'E1',
        'B3',
        sounds_like='acoustic bass guitar',
    ),
    # Sound-alike of the mandolin (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tambura_(Bulgaria) (redirects to the Balkan tambura page:
    # "It has doubled steel strings and is played with a plectrum, similar to mandolin and
    # bağlama"; "The Bulgarian tambura has 8 steel strings in 4 doubled courses. All the courses
    # are tuned in unison"; "The tambura has a long, narrow neck with typically 18 to 24
    # frets"). Range derived from the page: lowest D3 ("D3 D3, G3 G3, B3 B3, E4 E4"), highest E4
    # + 24 frets (the stated maximum) = E6
    CatalogEntry(
        'bulgarian tambura',
        'Bulgarian tambura',
        Family.PLUCKED_STRINGS,
        'D3',
        'E6',
        sounds_like='mandolin',
    ),
    # Sound-alike of the baritone guitar (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Fender_Bass_VI ("a six-string electric bass guitar"; "having
    # six strings tuned E1 to E3, an octave below the Spanish guitar"; "a shorter scale and
    # thinner strings"; "21 frets"): a six-string guitar-scale instrument an octave down, as the
    # baritone guitar is. Range derived from the page: lowest E1, highest E3 + 21 frets = C#5
    CatalogEntry(
        'electric bass vi',
        'Fender Bass VI',
        Family.PLUCKED_STRINGS,
        'E1',
        'C#5',
        sounds_like='baritone guitar',
    ),
    # Sound-alike of the ruan (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ruan_(instrument) ("soprano: gaoyinruan (高音阮, lit. "high
    # pitched ruan"; tuning: G3-D4-G4-D5)"; "The modern ruan has 24 frets with 12 semitones on
    # each string"): the soprano size of the ruan, no trait of its own given. Range derived from
    # the page: lowest G3, highest D5 + 24 frets = D7 (24 chromatic frets)
    CatalogEntry(
        'gaoyin ruan',
        'Gaoyinruan (soprano ruan)',
        Family.PLUCKED_STRINGS,
        'G3',
        'D7',
        sounds_like='ruan',
    ),
    # Sound-alike of the pipa (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Liuqin ("a three, four or five-stringed Chinese mandolin
    # with a pear-shaped body"; "played with a pick"; "The modern liuqin has four steel
    # strings"; "because of the diminutive size and resemblance of the liuqin to the pipa"): the
    # pipa is the nearest build. Range G3-G7: the common tuning "G-D-G-D", an octave above the
    # zhongruan (https://en.wikipedia.org/wiki/Ruan_(instrument)), as the sheet derives it
    CatalogEntry(
        'liuqin',
        'Liuqin',
        Family.PLUCKED_STRINGS,
        'G3',
        'G7',
        sounds_like='pipa',
    ),
    # Sound-alike of the domra (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Domra ("Instruments are made in various sizes including
    # piccolo, prima, alto, tenor, bass, and contrabass"; "Piccolo: b1 e2 a2") and
    # https://www.geidai.ac.jp/labs/koizumi/gcato/english/html-text/241.html ("strings: 3 steel
    # strings; 19 frets; 1 movable bridge"): the smallest domra, the prima's build. Range
    # derived from the sources: lowest B4, highest A5 + 19 frets = E7
    CatalogEntry(
        'piccolo domra',
        'Piccolo domra',
        Family.PLUCKED_STRINGS,
        'B4',
        'E7',
        sounds_like='domra',
    ),
    # Sound-alike of the tenor banjo (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Plectrum_banjo ("The four-string plectrum banjo is a
    # standard banjo without the short drone string. It usually has 22 frets on the neck";
    # "originally tuned C3 G3 B3 D4"; "tenor banjos and plectrum banjos are played with a
    # pick"): a four-string picked banjo, as the tenor banjo is. Range derived from the page:
    # lowest C3, highest D4 + 22 frets = C6
    CatalogEntry(
        'plectrum banjo',
        'Plectrum banjo',
        Family.PLUCKED_STRINGS,
        'C3',
        'C6',
        sounds_like='tenor banjo',
    ),
    # Sound-alike of the classical guitar (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Requinto_guitar ("a smaller version of a classical guitar,
    # with a scale length between 52-54cm. It is tuned a fourth higher than a standard classical
    # guitar, to A2-D3-G3-C4-E4-A4") and https://en.wikipedia.org/wiki/Guitar ("Standard
    # classical guitars have 19 frets"): a small classical guitar. Range derived from the
    # sources: lowest A2, highest A4 + 19 frets = E6
    CatalogEntry(
        'requinto guitar',
        'Requinto guitar',
        Family.PLUCKED_STRINGS,
        'A2',
        'E6',
        sounds_like='classical guitar',
    ),
    # Sound-alike of the ruan (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ruan_(instrument) ("bass: daruan (大阮, lit. "large ruan";
    # tuning: D2-A2-D3-A3)"; "The modern ruan has 24 frets with 12 semitones on each string"):
    # the bass size of the ruan, no trait of its own given. Range derived from the page: lowest
    # D2, highest A3 + 24 frets = A5 (24 chromatic frets)
    CatalogEntry(
        'daruan',
        'Daruan (bass ruan)',
        Family.PLUCKED_STRINGS,
        'D2',
        'A5',
        sounds_like='ruan',
    ),
    # Sound-alike of the banjo (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Sanxian ("the body is traditionally made from snake skin
    # stretched over a rounded rectangular resonator"; "The sanxian has a dry, somewhat
    # percussive tone and loud volume similar to the banjo. The larger sizes have a range of
    # three octaves"; "players popularly use steel strings"): the banjo is the nearest build.
    # Range derived from the page: "Large sanxian: G-d-g" (G2 D3 G3), three octaves above the
    # lowest string = G5
    CatalogEntry(
        'sanxian',
        'Sanxian',
        Family.PLUCKED_STRINGS,
        'G2',
        'G5',
        sounds_like='banjo',
    ),
    # Sound-alike of the balalaika (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Balalaika ("| secunda | 68-74 cm (27-29 in) | A3 A3 D4";
    # "Secundas are often the same instrument as primas, just tuned to a lower pitch range"; "in
    # professional orchestra-like ones that number raises to 24") and
    # https://www.geidai.ac.jp/labs/koizumi/gcato/english/html-text/242.html ("24 frets set into
    # the neck"): the prima's build, tuned lower. Range derived from the sources: lowest A3,
    # highest D4 + 24 frets = D6
    CatalogEntry(
        'secunda balalaika',
        'Secunda balalaika',
        Family.PLUCKED_STRINGS,
        'A3',
        'D6',
        sounds_like='balalaika',
    ),
    # Sound-alike of the pipa (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Setar ("a member of the tanbur family of long-necked lutes
    # with a range of more than two and a half octaves"; "The right hand plays the setar,
    # usually using only the index finger") and
    # https://www.geidai.ac.jp/labs/koizumi/gcato/english/html-text/252.html ("strings: 4, steel
    # and brass"; "frets:24, tied to the neck"; "range: ca. c-g""): single metal strings plucked
    # with a fingernail, as the pipa is. The record's range is approximate (C3-G5)
    CatalogEntry(
        'setar',
        'Setar',
        Family.PLUCKED_STRINGS,
        'C3',
        'G5',
        sounds_like='pipa',
    ),
    # Sound-alike of the electric guitar (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Seven-string_guitar ("adds one string to the more common
    # six-string guitar, commonly used to extend the bass range (usually a low B)") and
    # https://www.ibanez.com/usa/products/detail/rg7420ex_1p_01.html ("number of frets 24";
    # "factory tuning 1E,2B,3G,4D,5A,6E,7B"): a solid-body electric guitar with one more string.
    # Range derived from the sources: lowest B1, highest E4 + 24 frets = E6
    CatalogEntry(
        'seven string guitar',
        'Seven-string guitar (extended range)',
        Family.PLUCKED_STRINGS,
        'B1',
        'E6',
        sounds_like='electric guitar',
    ),
    # Sound-alike of the soprano ukulele (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ukulele ("Less common are the sopranino (also called
    # piccolo, bambino, or "pocket uke")"; the size chart: "| Pocket | piccolo, sopranino,
    # sopranissimo | 16 in (41 cm) | 11 in (28 cm) | 10-12 | G4-D6 (E6) | D5 G4 B4 E5"): a
    # smaller soprano ukulele, no other sound trait sourced. Range G4-D6 from the chart
    CatalogEntry(
        'sopranino ukulele',
        'Sopranino (pocket) ukulele',
        Family.PLUCKED_STRINGS,
        'G4',
        'D6',
        sounds_like='soprano ukulele',
    ),
    # Sound-alike of the classical guitar (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Terz_guitar ("refers to either a small sized classical
    # guitar or to the practice of tuning a standard guitar a minor third higher than standard
    # guitar tuning"; "The scale length is generally 530 mm") and
    # https://en.wikipedia.org/wiki/Guitar ("Standard classical guitars have 19 frets"): a small
    # classical guitar. Range derived from the sources: lowest E2 + 3 semitones = G2, highest E4
    # + 3 + 19 frets = D6
    CatalogEntry(
        'terz guitar',
        'Terz guitar',
        Family.PLUCKED_STRINGS,
        'G2',
        'D6',
        sounds_like='classical guitar',
    ),
    # Sound-alike of the greek bouzouki (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bouzouki ("The early bouzoukia mostly had three courses (six
    # strings in three pairs, known as trichordo)"; "most bouzoukis have the same number of
    # frets (27)"; infobox range "C3 - E6 (tetrachordo), D3 - E6 (trichordo)"): the three-course
    # form of the same instrument. Range D3-E6 as the infobox states it
    CatalogEntry(
        'trichordo bouzouki',
        'Trichordo bouzouki',
        Family.PLUCKED_STRINGS,
        'D3',
        'E6',
        sounds_like='greek bouzouki',
    ),
    # Sound-alike of the tiple colombiano (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Viola_da_terra ("Its 12 or 15 metal strings are arranged in
    # either five or six courses"; "the lower 2 courses have 3 strings each (2 of them high
    # octaves and the third a low octave)"; "22-24 metal frets"; "It is tuned A3 A3 A2•D4 D4
    # D3•G3 G4•B3 B3•D4 D4"): metal courses of three with two octave strings above a low one,
    # the trait of this sheet's tiple colombiano. Range derived from the page (12 strings):
    # lowest A2, highest D4 + 24 frets = D6
    CatalogEntry(
        'viola da terra',
        'Viola da terra',
        Family.PLUCKED_STRINGS,
        'A2',
        'D6',
        sounds_like='tiple colombiano',
    ),
    # Sound-alike of the ruan (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ruan_(instrument) ("xiaoruan (小阮, lit. "small ruan"; tuning:
    # D3-A3-D4-A4)"; "The modern ruan has 24 frets with 12 semitones on each string"): the alto
    # size of the ruan, no trait of its own given. Range derived from the page: lowest D3,
    # highest A4 + 24 frets = A6 (24 chromatic frets)
    CatalogEntry(
        'xiaoruan',
        'Xiaoruan (alto ruan)',
        Family.PLUCKED_STRINGS,
        'D3',
        'A6',
        sounds_like='ruan',
    ),
    # Sound-alike of the zither (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Zither ("The Alpine zither has 42 strings, and differs from the
    # concert zither primarily in requiring the addition of an extension to the body of the
    # instrument to support both the longer additional contrabass strings and their tuners"; "Alpine
    # zithers are tuned in a similar manner to the concert zither"; melody strings "plucked with a
    # plectrum on the right thumb"). Range derived from the page's tuning chart and
    # https://austria-forum.org/af/AEIOU/Zither/Zither_english ("5 melody strings across a
    # chromatic finger-board arranged in 29 frets"): lowest F1 (string 42), highest A4 + 29 frets
    # = D7. The longer contrabass strings are a range, not a sound trait
    CatalogEntry(
        'alpine zither',
        'Alpine zither',
        Family.PLUCKED_STRINGS,
        'F1',
        'D7',
        sounds_like='zither',
    ),
    # Sound-alike of the kantele (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Kantele ("The most typical and traditional tuning of the
    # five-string small kantele is just intonation arrived at via five-limit tuning, often in D
    # major or D minor"). Range from https://www.researchcatalogue.net/view/3968595/4045085 ("Most
    # small kanteles currently made in Finland are designed for D tuning, with the tonic (string 1)
    # tuned to D4") and https://www.researchcatalogue.net/view/3968595/3976467 ("the first five
    # notes of the D major scale"): open strings D4 E4 F#4 G4 A4, no frets, so the tuning is the
    # range
    CatalogEntry(
        'five string kantele',
        'Five-string kantele',
        Family.PLUCKED_STRINGS,
        'D4',
        'A4',
        sounds_like='kantele',
    ),
    # Sound-alike of the kantele (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Gusli ("the oldest East Slavic multi-string plucked instrument,
    # belonging to the zither family"; "Folk Gusli have from eleven to thirty-six gut or metal
    # strings, tuned diatonically"; "strumming all the strings with his right hand"). A Baltic
    # psaltery with the kantele (https://en.wikipedia.org/wiki/Kantele). Range from the infobox
    # ("Russian traditional tuning: E3 A3 H3 C4 D4 E4 F4 G4 A4", H is B): open strings only, so the
    # tuning is the range
    CatalogEntry(
        'gusli',
        'Gusli',
        Family.PLUCKED_STRINGS,
        'E3',
        'A4',
        sounds_like='kantele',
    ),
    # Sound-alike of the Chapman Stick (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Harpejji ("an electric 12-to-24-stringed musical instrument";
    # "primarily played with a two-handed tapping technique. It differs from other tapping
    # instruments, such as the Chapman Stick, by way of the orientation of the instrument to the
    # player"). Range: "the G16, a smaller 16-string model with a four-octave range (from C2 to
    # C6)", the G16's; the 24-string models' range is not given
    CatalogEntry(
        'harpejji',
        'Harpejji',
        Family.PLUCKED_STRINGS,
        'C2',
        'C6',
        sounds_like='chapman stick',
    ),
    # Sound-alike of the kantele (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Kankles ("Concert kanklės, with an expanded range of more
    # than four octaves (29 strings, C3-C7) and added chromaticism, provided by means of metal
    # levers at the side of the instrument"; "played with the fingers or with a pick made of bone
    # or quill"). A Baltic psaltery like the kantele (https://en.wikipedia.org/wiki/Kantele); the
    # levers are not a sound trait. Range C3-C7 as stated
    CatalogEntry(
        'concert kankles',
        'Concert kanklės',
        Family.PLUCKED_STRINGS,
        'C3',
        'C7',
        sounds_like='kantele',
    ),
    # Sound-alike of the koto (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ichigenkin ("An open-backed two string version, called the
    # azuma-ryu nigenkin (Eastern school two string zither)") and
    # https://www.geidai.ac.jp/labs/koizumi/english/gcato/html-text/207.html ("strings: 2, silk";
    # "range :e-a#''; tuning : e-e; scale;chromatic"; "plucks either one of two strings at a time
    # with the nail of the right hand index finger"). Range e-a#'' (Helmholtz) is E3-A#5. Silk
    # strings plucked with the nail, as the koto
    CatalogEntry(
        'nigenkin',
        'Azuma-ryū nigenkin',
        Family.PLUCKED_STRINGS,
        'E3',
        'A#5',
        sounds_like='koto',
    ),
    # Sound-alike of the appalachian dulcimer (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Siter ("The siter and celempung each have between 11 and 13
    # pairs of strings"; "played with the thumbnails") and
    # https://www.geidai.ac.jp/labs/koizumi/english/gcato/html-text/225.html ("strings: 12 double
    # courses, steel"; "range: Ca. 2 oct.form d"). Range: from d (Helmholtz, D3) about two
    # octaves, D3-D5, approximate as the record says, the gamelan scales not being equal-tempered.
    # Paired steel strings on a box zither: the catalog's only paired-course plucked zither
    CatalogEntry(
        'siter',
        'Siter',
        Family.PLUCKED_STRINGS,
        'D3',
        'D5',
        sounds_like='appalachian dulcimer',
    ),
    # Sound-alike of the appalachian dulcimer (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ichigenkin ("A two-string version called a yakumogoto (eight
    # cloud zither) was developed in 1820 by Nakayama Kotonushi. This instrument had a closed back
    # resonant body") and
    # https://www.geidai.ac.jp/labs/koizumi/english/gcato/html-text/206.html ("range :e-a#''; tuning
    # : e-e; scale;chromatic"; "Both strings are plucked simultaneously with a ryuso (pick)"). Range
    # e-a#'' (Helmholtz) is E3-A#5. Two strings tuned alike plucked with a pick is a unison pair, as
    # the appalachian dulcimer; no source names the string material
    CatalogEntry(
        'yakumogoto',
        'Yakumogoto',
        Family.PLUCKED_STRINGS,
        'E3',
        'A#5',
        sounds_like='appalachian dulcimer',
    ),
)
