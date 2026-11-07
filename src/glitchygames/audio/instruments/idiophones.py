"""Idiophones other than the tuned percussion bars and bells: plucked (and, later, friction).

An idiophone is an instrument whose own body is the vibrating, sounding part
(Hornbostel-Sachs class 1). The Hornbostel-Sachs list of idiophones is at
https://en.wikipedia.org/wiki/List_of_idiophones_by_Hornbostel%E2%80%93Sachs_number

Plucked idiophones (Hornbostel-Sachs 12) are a set of metal tongues, or lamellae, each fixed at
one end, plucked and left to ring: the kalimba and mbira with a thumb, the music box with the
pins of a revolving cylinder. A clamped tine rings at 1 : 6.27 of its fundamental (see
``percussion.TINE_RATIOS``), so each is built as a struck bar with those two partials.
"""

from __future__ import annotations

from functools import partial
from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family, Tag
from glitchygames.audio.instruments.percussion import TINE_RATIOS, struck_bar

# --- Plucked idiophones ---------------------------------------------------------------------

PLUCKED_IDIOPHONES: Final[tuple[CatalogEntry, ...]] = (
    # Range: https://www.thomann.co.uk/sela_kalimba_17_solid_sapelli.htm (a 17-tine kalimba in
    # C major: "Range: C' - E'''", C4 - E6)
    # Sound: https://en.wikipedia.org/wiki/Mbira ("clear, percussive, chimelike")
    CatalogEntry(
        'kalimba',
        'Kalimba',
        Family.PLUCKED_IDIOPHONES,
        'C4',
        'E6',
        partial(
            struck_bar,
            TINE_RATIOS,
            (1.0, 0.15),
            ring_seconds=1.5,
            mallet=0.08,
            mallet_low_pass=5000.0,
        ),
    ),
    # Range: kept from the catalog, because no fetched source gives an absolute mbira range
    # (the mbira page says only "Varies, see Tuning"); nothing fetched shows G2 - D5 wrong
    # Sound: https://en.wikipedia.org/wiki/Mbira
    CatalogEntry(
        'mbira',
        'Mbira',
        Family.PLUCKED_IDIOPHONES,
        'G2',
        'D5',
        partial(
            struck_bar,
            TINE_RATIOS,
            (1.0, 0.2),
            ring_seconds=1.5,
            mallet=0.15,
            mallet_low_pass=6000.0,
        ),
    ),
    # Range: kept from the catalog, because no fetched source gives the comb's note names (a
    # music box's notes sit "within 3 octaves of the song" per
    # https://donuma-shop.reamaze.com/kb/music-boxes/what-are-the-music-box-limitations,
    # consistent with the three octaves C4 - C7 but not proof of its ends)
    # Sound: https://en.wikipedia.org/wiki/Music_box (pins "pluck the tuned teeth (or lamellae)
    # of a steel comb")
    CatalogEntry(
        'music box',
        'Music box',
        Family.PLUCKED_IDIOPHONES,
        'C4',
        'C7',
        partial(
            struck_bar,
            TINE_RATIOS,
            (1.0, 0.2),
            ring_seconds=1.2,
            mallet=0.03,
            mallet_low_pass=8000.0,
        ),
        tags=frozenset({Tag.MECHANICAL}),
    ),
    # Range: the factory tuning ("A minor (a' - c'' - c' - a' - a - f' - e' - e'' - h')", nine
    # tines; Helmholtz a = A3, e'' = E5) at
    # https://www.soundcreation.eu/kalimba-cid688/hokema-sansula-renaissance-id77285.html
    # Sound: the same page ("a wonderful, delicate sound rich in harmonics") and
    # https://www.manufactum.com/sansula-renaissance-a15771/ (nine steel tongues on a frame with a
    # drum skin). No source gives tine partial ratios or ring times: the levels, ring and mallet
    # are sound design, chosen to be audibly different from the kalimba
    CatalogEntry(
        'sansula',
        'Sansula',
        Family.PLUCKED_IDIOPHONES,
        'A3',
        'E5',
        partial(
            struck_bar,
            TINE_RATIOS,
            (1.0, 0.3),
            ring_seconds=4.0,
            mallet=0.03,
            mallet_low_pass=3000.0,
        ),
    ),
)
