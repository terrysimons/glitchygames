"""Noise makers: free aerophones and horns, instruments that make a signal rather than a note.

A free aerophone (Hornbostel-Sachs 41) is set sounding by moving it through the air: whips,
bullroarers, sirens. An interruptive or reed free aerophone (412) is a horn: a reed or
diaphragm chops a stream of air or current into a buzz. The Hornbostel-Sachs aerophone list is
at https://en.wikipedia.org/wiki/List_of_aerophones_by_Hornbostel%E2%80%93Sachs_number

Each one here is unpitched: it ignores the pitch it is given, as a drum does, so each is built
with ``drum``.
"""

from __future__ import annotations

from functools import partial
from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import Tone, drum

NOISE_MAKERS: Final[tuple[CatalogEntry, ...]] = (
    # Sound: https://en.wikipedia.org/wiki/Whipcracking (the crack occurs when "a section of the
    # whip moves faster than the speed of sound", a small sonic boom)
    # The 10 ms ring, 3 kHz high-pass and drive are sound design: they make it clearly sharper
    # than the catalog "whip" (0.03 s, 1 kHz, drive 2), which imitates the slapstick
    CatalogEntry(
        'whip crack',
        'Whip crack (bullwhip)',
        Family.NOISE_MAKERS,
        None,
        None,
        partial(
            drum,
            noise=1.0,
            noise_ring_seconds=0.01,
            noise_high_pass=3000.0,
            tail=0.02,
            drive=6.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Foghorn (the diaphone "could emit extremely powerful
    # low-frequency notes"; the page gives no frequency)
    # The 110 Hz fundamental, the 2.0 s ring, the 600 Hz low-pass and the drive are sound design
    CatalogEntry(
        'diaphone',
        'Diaphone foghorn',
        Family.NOISE_MAKERS,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=110.0, ring_seconds=2.0, wave='saw'),),
            noise=0.1,
            noise_ring_seconds=2.0,
            noise_low_pass=600.0,
            tail=0.4,
            drive=3.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Air_horn (compressed air flows "past the reed or
    # diaphragm"; a single horn)
    # The 330 Hz tone, the 1.5 s ring and the drive are sound design: the page gives no frequency
    CatalogEntry(
        'air horn',
        'Air horn',
        Family.NOISE_MAKERS,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=330.0, ring_seconds=1.5, wave='saw'),),
            tail=0.2,
            drive=4.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Vehicle_horn ("Typical frequencies of a pair of horns
    # of this design are 500 Hz and 405-420 Hz": 500 Hz and 412 Hz, the middle of the second
    # range, are sourced; the 1.0 s ring and the short tail are sound design)
    CatalogEntry(
        'vehicle horn',
        'Electric vehicle horn',
        Family.NOISE_MAKERS,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=500.0, ring_seconds=1.0, wave='square'),
                Tone(hertz=412.0, ring_seconds=1.0, wave='square'),
            ),
            tail=0.05,
            drive=2.0,
        ),
    ),
    # Sound: https://en.wikipedia.org/wiki/Party_horn (it "produces a horn-like noise when a
    # person blows into it"; H-S 412.131, individual free reeds; no pitch is given)
    # The 880 Hz tone, the 0.25 s ring and the drive are sound design
    CatalogEntry(
        'party horn',
        'Party horn',
        Family.NOISE_MAKERS,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=880.0, ring_seconds=0.25, wave='square'),),
            tail=0.05,
            drive=3.0,
        ),
    ),
)
