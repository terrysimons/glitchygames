"""Tuned percussion: mallets, bells, pans, timpani and gamelan.

Tuned percussion's partials are not harmonics. A free bar (glockenspiel) rings at 1 : 2.76 :
5.40 : 8.93 of its fundamental; marimba and vibraphone bars are cut so the first overtone is
the fourth harmonic and the xylophone's the third; a tubular bell's and a carillon bell's
partials (hum, prime, tierce and nominal; the weak quint is left out) give the bell's
minor-third colour; a tubular bell's struck note is heard an octave below its fourth mode, which
with the fifth and sixth rings near 2 : 3 : 4 of that note; steel pans and handpans are tuned to
the octave and twelfth; a timpani's head favours 1 : 1.5 : 2 (Rossing, *Science of Percussion
Instruments*; Fletcher and Rossing, *The Physics of Musical
Instruments*). Untuned percussion (drums, cymbals) is the drums and percussion family, in
``drums.py``.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import Partial, struck
from glitchygames.audio.instruments.tuned_sound_alikes import TUNED_SOUND_ALIKES

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

# A gamelan key's or singing bowl's second partial (a measured ratio, not e)
SINGING_METAL_SECOND_PARTIAL: Final[float] = 2.71  # ruff: ignore[math-constant] - measured, not e

# --- Tuned percussion -----------------------------------------------------------------------


def struck_bar(  # ruff: ignore[too-many-arguments] - a struck bar's partials
    ratios: tuple[float, ...],
    levels: tuple[float, ...],
    *,
    ring_seconds: float,
    mallet: float = 0.05,
    mallet_low_pass: float = 3000.0,
    overtone_ring: float = 0.25,
) -> Instrument:
    """A struck or plucked bar: a fundamental and its overtones, each ringing out on its own.

    Args:
        ratios: Each partial's frequency as a multiple of the note's.
        levels: Each partial's level, one per ratio.
        ring_seconds: How long the fundamental rings (it is also the release).
        mallet: Seconds of the mallet's noise burst.
        mallet_low_pass: Cutoff in hertz of the mallet's noise.
        overtone_ring: The overtones' ring time as a fraction of the fundamental's, divided by
            the overtone's number.

    Returns:
        The instrument.
    """
    partials = tuple(
        Partial(
            ratio=ratio,
            level=level,
            ring_seconds=ring_seconds if number == 0 else ring_seconds * overtone_ring / number,
        )
        for number, (ratio, level) in enumerate(zip(ratios, levels, strict=True))
    )
    return struck(partials, release=ring_seconds, mallet=mallet, mallet_low_pass=mallet_low_pass)


# Instruments sounding up to C8 (4186 Hz) keep their partials below 5x, under the Nyquist
# limit at 44.1 kHz (the free bar's third partial, 5.40x, would pass it there)
FREE_BAR_RATIOS: Final[tuple[float, ...]] = (1.0, 2.76)
# A clamped tine's first two modes (its third, 17.55x, is past hearing for most of its notes)
TINE_RATIOS: Final[tuple[float, ...]] = (1.0, 6.27)
GLOCKENSPIEL = partial(
    struck_bar,
    FREE_BAR_RATIOS,
    (1.0, 0.45),
    ring_seconds=2.5,
    mallet=0.06,
    mallet_low_pass=8000.0,
    overtone_ring=0.5,
)
XYLOPHONE = partial(
    struck_bar,
    (1.0, 3.0),
    (1.0, 0.35),
    ring_seconds=0.6,
    mallet=0.1,
    mallet_low_pass=6000.0,
    overtone_ring=0.5,
)
MARIMBA = partial(
    struck_bar,
    (1.0, 4.0, 9.9),
    (1.0, 0.25, 0.06),
    ring_seconds=1.2,
    mallet=0.04,
    mallet_low_pass=2000.0,
)
VIBRAPHONE = partial(
    struck_bar,
    (1.0, 4.0, 10.0),
    (1.0, 0.22, 0.05),
    ring_seconds=4.0,
    mallet=0.03,
    mallet_low_pass=3000.0,
    overtone_ring=0.15,
)
GAMELAN_METALLOPHONE = partial(
    struck_bar,
    (1.0, SINGING_METAL_SECOND_PARTIAL, 5.15),
    (1.0, 0.4, 0.15),
    ring_seconds=3.0,
    mallet=0.06,
    mallet_low_pass=4000.0,
    overtone_ring=0.4,
)
KETTLE_GONG = partial(
    struck_bar,
    (1.0, 1.52, 2.0),
    (1.0, 0.35, 0.25),
    ring_seconds=2.0,
    mallet=0.05,
    mallet_low_pass=3000.0,
    overtone_ring=0.6,
)
HARMONIC_PAN = partial(
    struck_bar,
    (1.0, 2.0, 3.0),
    (1.0, 0.5, 0.25),
    ring_seconds=1.8,
    mallet=0.04,
    mallet_low_pass=3500.0,
    overtone_ring=0.5,
)


def _church_bell(*, ring_seconds: float) -> Instrument:
    # Hum (an octave below), prime, minor-third tierce and nominal (an octave above); the quint,
    # the weakest of a bell's five, is left out, as an instrument has at most four sources
    return struck(
        (
            Partial(ratio=0.5, level=0.6, ring_seconds=ring_seconds),
            Partial(ratio=1.0, level=0.8, ring_seconds=ring_seconds * 0.6),
            Partial(ratio=1.2, level=0.6, ring_seconds=ring_seconds * 0.5),
            Partial(ratio=2.0, level=1.0, ring_seconds=ring_seconds * 0.35),
        ),
        release=ring_seconds,
    )


def _tubular_bell() -> Instrument:
    return struck(
        (
            # A free tube's modes 3-6 (as (2n + 1) squared: 49, 81, 121, 169) over the struck note,
            # an octave below mode 4: nothing sounds at the note itself, the ear supplies it
            Partial(ratio=1.21, level=0.2, ring_seconds=1.5),
            Partial(ratio=2.0, level=1.0, ring_seconds=4.0),
            Partial(ratio=2.99, level=0.6, ring_seconds=3.0),
            Partial(ratio=4.17, level=0.4, ring_seconds=2.0),
        ),
        release=4.0,
    )


def _timpani() -> Instrument:
    return struck(
        (
            Partial(ratio=1.0, level=1.0, ring_seconds=2.5),
            Partial(ratio=1.5, level=0.5, ring_seconds=1.5),
            Partial(ratio=1.98, level=0.3, ring_seconds=1.0),
        ),
        release=2.0,
        mallet=0.25,
        mallet_low_pass=1500.0,
    )


_TUNED_BUILDS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry('glockenspiel', 'Glockenspiel', Family.TUNED_PERCUSSION, 'G5', 'C8', GLOCKENSPIEL),
    CatalogEntry(
        'crotales',
        'Crotales',
        Family.TUNED_PERCUSSION,
        'C6',
        'C8',
        partial(
            struck_bar,
            (1.0, 2.0, 3.0),
            (1.0, 0.3, 0.15),
            ring_seconds=4.0,
            mallet=0.05,
            mallet_low_pass=8000.0,
            overtone_ring=0.4,
        ),
    ),
    CatalogEntry('xylophone', 'Xylophone', Family.TUNED_PERCUSSION, 'F4', 'C8', XYLOPHONE),
    CatalogEntry('marimba', 'Marimba', Family.TUNED_PERCUSSION, 'C2', 'C7', MARIMBA),
    CatalogEntry('bass marimba', 'Bass marimba', Family.TUNED_PERCUSSION, 'A1', 'C4', MARIMBA),
    CatalogEntry('vibraphone', 'Vibraphone', Family.TUNED_PERCUSSION, 'F3', 'F6', VIBRAPHONE),
    CatalogEntry(
        'balafon',
        'Balafon',
        Family.TUNED_PERCUSSION,
        'C3',
        'C6',
        partial(
            struck_bar,
            (1.0, 4.0, 9.0),
            (1.0, 0.35, 0.1),
            ring_seconds=0.7,
            mallet=0.12,
            mallet_low_pass=4000.0,
        ),
    ),
    CatalogEntry(
        'tubular bells',
        'Tubular bells (chimes)',
        Family.TUNED_PERCUSSION,
        'C4',
        'F5',
        _tubular_bell,
    ),
    CatalogEntry(
        'church bell',
        'Church bell',
        Family.TUNED_PERCUSSION,
        'C3',
        'C5',
        partial(_church_bell, ring_seconds=6.0),
    ),
    CatalogEntry(
        'carillon',
        'Carillon',
        Family.TUNED_PERCUSSION,
        'C3',
        'C7',
        partial(_church_bell, ring_seconds=3.5),
    ),
    CatalogEntry(
        'handbells',
        'Handbells',
        Family.TUNED_PERCUSSION,
        'C5',
        'C8',
        partial(
            struck_bar,
            (1.0, 3.0, 5.0),
            (1.0, 0.25, 0.1),
            ring_seconds=2.5,
            mallet=0.02,
            overtone_ring=0.4,
        ),
    ),
    CatalogEntry(
        'tenor steel pan', 'Tenor steel pan', Family.TUNED_PERCUSSION, 'C4', 'E6', HARMONIC_PAN
    ),
    CatalogEntry(
        'double second steel pan',
        'Double second steel pan',
        Family.TUNED_PERCUSSION,
        'F#3',
        'Bb5',
        HARMONIC_PAN,
    ),
    CatalogEntry(
        'cello steel pan', 'Cello steel pan', Family.TUNED_PERCUSSION, 'C3', 'B4', HARMONIC_PAN
    ),
    CatalogEntry(
        'bass steel pan', 'Bass steel pan', Family.TUNED_PERCUSSION, 'A1', 'D3', HARMONIC_PAN
    ),
    CatalogEntry(
        'handpan',
        'Handpan',
        Family.TUNED_PERCUSSION,
        'D3',
        'A4',
        partial(
            struck_bar,
            (1.0, 2.0, 3.0),
            (1.0, 0.4, 0.3),
            ring_seconds=3.0,
            mallet=0.03,
            mallet_low_pass=1500.0,
            overtone_ring=0.6,
        ),
    ),
    CatalogEntry('timpani', 'Timpani', Family.TUNED_PERCUSSION, 'D2', 'C4', _timpani),
    CatalogEntry(
        'saron', 'Gamelan saron', Family.TUNED_PERCUSSION, 'C4', 'C5', GAMELAN_METALLOPHONE
    ),
    CatalogEntry(
        'gender', 'Gamelan gendèr', Family.TUNED_PERCUSSION, 'C3', 'C6', GAMELAN_METALLOPHONE
    ),
    CatalogEntry('bonang', 'Gamelan bonang', Family.TUNED_PERCUSSION, 'C4', 'C6', KETTLE_GONG),
    CatalogEntry(
        'tuned gong',
        'Tuned gong',
        Family.TUNED_PERCUSSION,
        'C2',
        'C4',
        partial(
            struck_bar,
            (1.0, 1.52, 2.0),
            (1.0, 0.35, 0.25),
            ring_seconds=5.0,
            mallet=0.05,
            mallet_low_pass=1000.0,
            overtone_ring=0.6,
        ),
    ),
    CatalogEntry(
        'singing bowl',
        'Singing bowl',
        Family.TUNED_PERCUSSION,
        'C3',
        'C5',
        partial(
            struck_bar,
            (1.0, SINGING_METAL_SECOND_PARTIAL, 5.15),
            (1.0, 0.5, 0.2),
            ring_seconds=8.0,
            mallet=0.02,
            mallet_low_pass=2000.0,
            overtone_ring=0.6,
        ),
    ),
    CatalogEntry(
        'tabla dayan',
        'Tabla (dayan)',
        Family.TUNED_PERCUSSION,
        'C4',
        'D5',
        partial(
            struck_bar,
            (1.0, 2.0, 3.0),
            (1.0, 0.5, 0.35),
            ring_seconds=0.6,
            mallet=0.15,
            mallet_low_pass=4000.0,
            overtone_ring=0.6,
        ),
    ),
    # --- Batch 5's bars, plaques, tubes and stones, in the order of
    # plans/data/instrument-audit/batch-5.tsv (the sheet's notes give each row's full quotes).
    # Boomwhackers: https://en.wikipedia.org/wiki/Boomwhacker (the sound source and the range
    # source): "lightweight, hollow, color-coded, plastic tubes, tuned to a musical pitch by
    # length"; "The pitch of the instrument is determined by the length of the tube"; "They are
    # most commonly hit with a hand, against the floor, or on other parts of the human body";
    # infobox "range = C2-G5". The traits are sourced: a hollow tube is an air column, so its
    # overtones are whole numbers (1 : 2, the second harmonic the only one kept), with no
    # resonator and a hand or floor strike's dull noise burst. Sound design (no fetched source
    # gives a number): the 0.15 level of the second harmonic, the 0.35 s ring, the 0.2 mallet
    # level and its 2500 Hz low pass, and the overtone ring of 0.4
    CatalogEntry(
        'boomwhackers',
        'Boomwhackers',
        Family.TUNED_PERCUSSION,
        'C2',
        'G5',
        partial(
            struck_bar,
            (1.0, 2.0),
            (1.0, 0.15),
            ring_seconds=0.35,
            mallet=0.2,
            mallet_low_pass=2500.0,
            overtone_ring=0.4,
        ),
    ),
    # Balinese gangsa (pemade): https://en.wikipedia.org/wiki/Gamelan_gong_kebyar (the sound
    # and range source) and https://en.wikipedia.org/wiki/Gangsa: "Each instrument consists of
    # several tuned metal bars (either iron or bronze) each placed over an individual
    # resonator. The bars are hit with a wooden panggul"; "these pairs are tuned to be
    # dissonant and create certain wavelengths of sympathetic vibrations to create a shimmering
    # tone (see Ombak)"; "one note on a female gangsa pemade might be tuned to 220 Hz, while
    # the male gangsa pemade might be tuned slightly higher to 228 Hz". Range: kantilan's "highest
    # note being around C7" over "a range of two octaves", and the pemade "exactly one octave
    # lower", so C4 to C6 (approximate: no standard pitch in Balinese music).
    # The ombak is the pair's two fundamentals 228 / 220 = 1.036 apart. CAVEAT for the owner: the
    # source gives a beat rate (8 Hz at 220 Hz) but the engine has one ratio, taken here at 220 Hz,
    # so the beating speeds up with pitch (about 38 Hz at C6) where a real pair beats at a rate
    # set by its tuning; a ratio is the nearest the engine has without a new feature. Sound
    # design: the 2.71 partial (GAMELAN_METALLOPHONE's, from the catalog), every level and ring,
    # the mallet. The sheet's build also holds a 5.15 partial, which does not fit: ``struck``
    # takes three partials with a mallet noise (a fourth source), so the weakest, 5.15, is left out
    CatalogEntry(
        'gangsa',
        'Balinese gangsa (pemadé)',
        Family.TUNED_PERCUSSION,
        'C4',
        'C6',
        partial(
            struck,
            (
                Partial(ratio=1.0, level=1.0, ring_seconds=3.0),
                Partial(ratio=1.036, level=0.8, ring_seconds=3.0),
                Partial(ratio=SINGING_METAL_SECOND_PARTIAL, level=0.4, ring_seconds=1.2),
            ),
            release=3.0,
            mallet=0.06,
            mallet_low_pass=4000.0,
        ),
    ),
)

# The family: its builds, then the sound-alikes that share them (``tuned_sound_alikes.py``)
TUNED_PERCUSSION: Final[tuple[CatalogEntry, ...]] = _TUNED_BUILDS + TUNED_SOUND_ALIKES
