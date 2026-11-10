"""Idiophones other than the tuned percussion bars and bells: plucked and rubbed.

An idiophone is an instrument whose own body is the vibrating, sounding part
(Hornbostel-Sachs class 1). The Hornbostel-Sachs list of idiophones is at
https://en.wikipedia.org/wiki/List_of_idiophones_by_Hornbostel%E2%80%93Sachs_number

Plucked idiophones (Hornbostel-Sachs 12) are a set of metal tongues, or lamellae, each fixed at
one end, plucked and left to ring: the kalimba and mbira with a thumb, the music box with the
pins of a revolving cylinder. A clamped tine rings at 1 : 6.27 of its fundamental (see
``percussion.TINE_RATIOS``), so each is built as a struck bar with those two partials.

Friction instruments (Hornbostel-Sachs 13) are set singing by rubbing: a wet finger on glass, a
rosined cylinder on a rod. The glass harmonica (bowls on a spindle) is built as a ``blown`` tone;
the glass harp and the terpodion use the ``rubbed`` shape (inharmonic partials that swell in and
hold).
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family, Tag
from glitchygames.audio.instruments.percussion import TINE_RATIOS, struck_bar
from glitchygames.audio.instruments.timbres import Partial, blown, rubbed

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

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

# --- Friction instruments -------------------------------------------------------------------

# A goblet's rim vibrates like a thin ring, whose bending modes (2, 3, 4 nodal diameters) sit at
# n(n^2 - 1) / sqrt(n^2 + 1): 1 : 2.83 : 5.42 of the lowest. That is the textbook thin-ring
# result (Rayleigh, Theory of Sound), worked out here, not read from a fetched source; real
# glasses deviate from it. Three partials: the highest, 5.42 x 1319 Hz (E6) = 7.1 kHz, is far
# below the Nyquist limit
GOBLET_RATIOS: Final[tuple[float, ...]] = (1.0, 2.83, 5.42)
# A free rod's bending modes: the free bar's 1 : 2.76 : 5.40. The source the code already cites
# for the free bar, ``percussion``'s module docstring (Rossing, *Science of Percussion
# Instruments*), gives 1 : 2.76 : 5.40 : 8.93; 5.40 is the free bar's third mode (5.404), which
# ``percussion.FREE_BAR_RATIOS`` leaves out (it holds only 1.0 and 2.76). Three partials keep F7
# (2794 Hz) under the Nyquist limit: a fourth, at 8.93x, would sit at 25 kHz
ROD_RATIOS: Final[tuple[float, ...]] = (1.0, 2.76, 5.40)


def _sustained_glass() -> Instrument:
    return blown((1.0, 0.04, 0.02), attack=0.25, release=0.6, chorus_cents=2.0)


FRICTION_INSTRUMENTS: Final[tuple[CatalogEntry, ...]] = (
    # Range: kept from the catalog (G3 - C6 lies inside Finkenbeiner's "F-37G- 3 Octaves. 37 notes
    # G3 to G6", https://finkenbeiner.com/catalog.html)
    # Sound: https://en.wikipedia.org/wiki/Glass_harmonica ("ethereal and haunting, with a
    # flute-like tone that can hold long notes"); the build is unchanged from before the move
    CatalogEntry(
        'glass harmonica',
        'Glass harmonica',
        Family.FRICTION_INSTRUMENTS,
        'G3',
        'C6',
        _sustained_glass,
    ),
    # Range: Kling, The Art of Instrumentation (1905), quoted at
    # https://en.wikipedia.org/wiki/Glass_harp ("The following is its usual compass: G3-E6")
    # Sound: the same page ("running moistened or chalked fingers around the rim of the glasses";
    # tone "very similar to the harmonics of a Zither"; a recording with "quick and clearly
    # articulated staccato notes"). The partials are a thin ring's (GOBLET_RATIOS); their
    # levels and the 0.08 s swell (quicker than the glass harmonica's 0.25 s) are sound design
    CatalogEntry(
        'glass harp',
        'Glass harp (musical glasses)',
        Family.FRICTION_INSTRUMENTS,
        'G3',
        'E6',
        partial(
            rubbed,
            tuple(
                Partial(ratio=ratio, level=level, ring_seconds=0.0)
                for ratio, level in zip(GOBLET_RATIOS, (1.0, 0.25, 0.1), strict=True)
            ),
            attack=0.08,
            release=0.3,
        ),
    ),
    # Range: the Buschmann terpodion's museum record, "Keyboard range: F1-f4 (six octaves)", read
    # as Helmholtz (contra F to four-lined f) = F1 - F7, at
    # https://en.wikipedia.org/wiki/Terpodion
    # Sound: the same page ("a friction idiophone, similar to the glass harmonica and
    # clavicylinder"; a rosined wooden cylinder and a friction rod). The rod partials are a free
    # rod's (ROD_RATIOS); their levels, the slow 0.6 s swell and the low-pass are sound design.
    # The page's "volume ... dependent on the amount of pressure applied to the keys" is a
    # playing trait (note volume), not modelled here
    CatalogEntry(
        'terpodion',
        'Terpodion',
        Family.FRICTION_INSTRUMENTS,
        'F1',
        'F7',
        partial(
            rubbed,
            tuple(
                Partial(ratio=ratio, level=level, ring_seconds=0.0)
                for ratio, level in zip(ROD_RATIOS, (1.0, 0.45, 0.2), strict=True)
            ),
            attack=0.6,
            release=0.5,
            low_pass=6000.0,
        ),
    ),
)
