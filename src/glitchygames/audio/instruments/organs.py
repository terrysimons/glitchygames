"""Organs: pipe organ stops, positive, combo and theatre organs, and the calliope.

Organs are drawbar registrations (``Harmonics.drawbars``) or pipe stops: a principal's every
harmonic, a flute stop's nearly pure tone, a reed stop's brassy one. Ranges are an organ's keys at
8' pitch (a 61-note manual, C2-C7), and a 16' stop or drawbar sounds an octave lower. A stop
sounds at its footage against its keys (16' an octave below, 4' an octave above, 2 2/3' a twelfth
above), through ``_pipe_stop``'s ``footage``. A self-playing organ carries ``Tag.MECHANICAL``. The
sound-alikes are in ``organ_sound_alikes.py``; the keyboards and electromechanical instruments are
in ``keyboards.py``.
"""

from __future__ import annotations

import math
from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.organ_sound_alikes import ORGAN_SOUND_ALIKES
from glitchygames.audio.instruments.timbres import (
    HIGHEST_HARMONIC,
    blown,
    drawbar_organ,
    falling_series,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.audio.instrument import Instrument


# A stop of 8' sounds at its key's pitch
UNISON_FOOTAGE: Final[float] = 8.0


def _pipe_stop(
    levels: tuple[float, ...],
    *,
    chiff: float,
    release: float = 0.15,
    footage: float = UNISON_FOOTAGE,
) -> Instrument:
    # The tone sounds at its footage against the key (16' an octave below, 4' an octave above);
    # the chiff is breath noise and stays
    return blown(
        levels,
        attack=0.04,
        release=release,
        breath=chiff,
        breath_low_pass=6000.0,
        semitones=12.0 * math.log2(UNISON_FOOTAGE / footage),
    )


PRINCIPAL_LEVELS: Final[tuple[float, ...]] = falling_series(count=16, decibels_per_octave=6.5)
FLUTE_STOP_LEVELS: Final[tuple[float, ...]] = (1.0, 0.1, 0.12, 0.02, 0.02)
REED_STOP_LEVELS: Final[tuple[float, ...]] = falling_series(count=28, decibels_per_octave=2.5)
STRING_STOP_LEVELS: Final[tuple[float, ...]] = falling_series(count=28, decibels_per_octave=4.0)
CALLIOPE_LEVELS: Final[tuple[float, ...]] = (1.0, 0.25, 0.2, 0.05)
# A stopped flue pipe: FLUTE_STOP_LEVELS with the even harmonics silent. The missing even
# harmonics are sourced (Audsley, The Organ of the Twentieth Century, 1919,
# https://archive.org/download/organoftwentieth00audsuoft/organoftwentieth00audsuoft_djvu.txt:
# "Covered pipes cannot give the uneven upper partial tones, such as the first or octave and the
# third or super-octave, etc.", counting upper partials from the octave, so harmonics 2 and 4);
# the odd harmonics' levels are sound design, copied from FLUTE_STOP_LEVELS
STOPPED_FLUTE_LEVELS: Final[tuple[float, ...]] = (1.0, 0.0, 0.12, 0.0, 0.02)
# A reed with a closed cylindrical resonator: REED_STOP_LEVELS' slope with the even harmonics
# silent. The resonator's odd harmonics are sourced (the Encyclopedia of Organ Stops,
# http://www.organstops.org/c/Clarinet.html: "The Clarinet is usually constructed with
# half-length cylindrical metal resonators, which reinforce the odd-numbered harmonics (as with a
# stopped flue pipe)"); the slope and the silent evens are sound design, as the batch 13 plan
# rules them in plans/2026-11-12-instrument-catalog-batch-13-implementation.md
CLOSED_REED_LEVELS: Final[tuple[float, ...]] = falling_series(
    count=28, decibels_per_octave=2.5, odd_only=True
)


def compound_stop_levels(levels: Sequence[float], footages: Sequence[float]) -> tuple[float, ...]:
    """One wave's levels for a compound stop: each rank's levels at its harmonic of the key.

    A rank of footage f sounds harmonic 8 / f of an 8' key (4' the octave, 2 2/3' the twelfth,
    1 3/5' the seventeenth), so its harmonic n lands on harmonic n x 8 / f. The ranks are summed
    and the loudest level made 1.0 (the batch 13 plan's footage ruling, rule 4:
    plans/2026-11-12-instrument-catalog-batch-13-implementation.md).

    Args:
        levels: Each rank's harmonic levels, the fundamental first (the same for every rank).
        footages: Each rank's footage in feet.

    Returns:
        The summed levels, harmonic 1 first, the loudest 1.0.

    Raises:
        ValueError: On empty levels or footages, a footage that is not above zero, a rank whose
            footage is not 8 / n feet for a whole n, or whose levels would reach above the
            highest harmonic a wave holds.
    """
    if not levels:
        message = 'a compound stop needs at least one harmonic level'
        raise ValueError(message)
    if not footages:
        message = 'a compound stop needs at least one rank'
        raise ValueError(message)
    rank_harmonics: list[int] = []
    for footage in footages:
        if footage <= 0.0:
            message = f"a rank's footage must be above zero, not {footage}"
            raise ValueError(message)
        harmonic = UNISON_FOOTAGE / footage
        if not harmonic.is_integer():
            message = f"a {footage}' rank does not sound a harmonic of the key"
            raise ValueError(message)
        rank_harmonics.append(int(harmonic))
    highest = max(rank_harmonic * len(levels) for rank_harmonic in rank_harmonics)
    if highest > HIGHEST_HARMONIC:
        message = f'the ranks reach harmonic {highest}, above harmonic {HIGHEST_HARMONIC}'
        raise ValueError(message)
    summed = [0.0] * highest
    for rank_harmonic in rank_harmonics:
        for index, level in enumerate(levels):
            summed[(index + 1) * rank_harmonic - 1] += level
    loudest = max(summed)
    return tuple(level / loudest for level in summed)


_ORGAN_BUILDS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'pipe organ principal',
        "Pipe organ, principal 8'",
        Family.ORGANS,
        'C2',
        'C7',
        partial(_pipe_stop, PRINCIPAL_LEVELS, chiff=0.01),
    ),
    CatalogEntry(
        'pipe organ flute',
        "Pipe organ, flute 8'",
        Family.ORGANS,
        'C2',
        'C7',
        partial(_pipe_stop, FLUTE_STOP_LEVELS, chiff=0.02),
    ),
    CatalogEntry(
        'pipe organ reed',
        "Pipe organ, trumpet 8'",
        Family.ORGANS,
        'C2',
        'C7',
        partial(_pipe_stop, REED_STOP_LEVELS, chiff=0.0),
    ),
    CatalogEntry(
        'pipe organ string',
        "Pipe organ, viola da gamba 8'",
        Family.ORGANS,
        'C2',
        'C7',
        partial(_pipe_stop, STRING_STOP_LEVELS, chiff=0.0),
    ),
    CatalogEntry(
        'pipe organ plenum',
        'Pipe organ, full (plenum)',
        Family.ORGANS,
        'C2',
        'C7',
        partial(drawbar_organ, '868868868', attack=0.04, release=0.3),
    ),
    CatalogEntry(
        'positive organ',
        'Positive organ',
        Family.ORGANS,
        'C2',
        'C6',
        partial(drawbar_organ, '008505000', attack=0.03, release=0.1),
    ),
    CatalogEntry(
        'combo organ',
        'Combo organ',
        Family.ORGANS,
        'C2',
        'C7',
        partial(
            blown,
            falling_series(count=20, decibels_per_octave=3.0, even_level=0.3),
            attack=0.003,
            release=0.03,
        ),
    ),
    CatalogEntry(
        'theatre organ',
        'Theatre organ (tibia)',
        Family.ORGANS,
        'C2',
        'C7',
        partial(blown, FLUTE_STOP_LEVELS, attack=0.03, release=0.2, chorus_cents=6.0),
    ),
    CatalogEntry(
        'calliope',
        'Calliope',
        Family.ORGANS,
        'C3',
        'G5',
        partial(
            blown, CALLIOPE_LEVELS, attack=0.02, release=0.1, breath=0.05, breath_low_pass=7000.0
        ),
    ),
    # --- Batch 13's organ stops, in the order of plans/data/instrument-audit/batch-13.tsv. A
    # stop's range is its keys at 8' pitch, and the stop sounds at its footage against them.
    # The manual compass, for the stops that play from a manual: the Pipe organ page
    # (https://en.wikipedia.org/wiki/Pipe_organ, its Keyboards paragraph, cited there to the
    # American Guild of Organists' Pipe Organ Guide, in Helmholtz notation): "Most current
    # specifications call for two or more manuals with sixty-one notes (five octaves, from C to
    # c⁗)"; the cited guide (archived,
    # https://web.archive.org/web/20070927154656/http://www.agohq.org/guide/pages/pages_5_5/frameset01.html):
    # "Most American organs have 61 notes on the manuals-to C above high C"; and the AGO's
    # Standard Console Guidelines as Organ Supply Industries reproduces them
    # (https://www.organsupply.com/assets/Brochures/Console-Tri-Fold.pdf): "Compass: CC to c4, 61
    # notes." C is C2 and c⁗ is C7, 61 keys.
    # The cornet, a compound stop: the Encyclopedia of Organ Stops
    # (http://www.organstops.org/c/Cornet.html): "In its quintessential form, the Cornet is a
    # wide-scaled compound stop without breaks, containing a third-sounding rank, often of short
    # (treble) compass."; of the classical French Cornet, "It was a solo stop, almost invariably
    # composed of the following five ranks:" Bourdon 8', Prestant 4', Nasard 2-2/3', Quarte de
    # Nasard 2' and Tierce 1-3/5', "The ranks were all of wide scale, and all open except for the
    # 8'." and "It was invariably of short compass, usually from middle C upwards." Audsley,
    # Organ-Stops and Their Artistic Registration (1921, https://archive.org/download/cu31924086010331/cu31924086010331_djvu.txt):
    # "The compound tone of the Cornet was, on account of the large scale of its pipes, flutey in
    # character" and "Being unbroken in its ranks". So the five ranks are harmonics 1, 2, 3, 4 and
    # 5 of the key, one wave (compound_stop_levels) at 8'. Range: middle C (C4), from the stop's
    # own source, up to the manual's top key, C7.
    # Sourced: the five unbroken ranks, their flute tone and the compass from middle C. Sound
    # design: each rank's levels (FLUTE_STOP_LEVELS, the same for every rank) and chiff, copied
    # from pipe organ flute. One table serves every rank, the stopped 8' rank included, because
    # that rank's missing even harmonics (FLUTE_STOP_LEVELS' 0.02 at harmonic 4) lie under the 4'
    # and 2' ranks' fundamentals, so one table for every rank changes nothing audible (the sheet's
    # ruling, plans/data/instrument-audit/batch-13.tsv). The middle C compass is the Encyclopedia's
    # alone; Audsley's quotes here are not cited for it
    CatalogEntry(
        'cornet organ',
        'Cornet V',
        Family.ORGANS,
        'C4',
        'C7',
        partial(
            _pipe_stop,
            compound_stop_levels(FLUTE_STOP_LEVELS, (8.0, 4.0, 8.0 / 3.0, 2.0, 1.6)),
            chiff=0.02,
        ),
    ),
    # The clarinet stop: the Encyclopedia of Organ Stops
    # (http://www.organstops.org/c/Clarinet.html): "The Clarinet is usually constructed with
    # half-length cylindrical metal resonators, which reinforce the odd-numbered harmonics (as
    # with a stopped flue pipe), and give the stop much of its characteristic hollow tone." and
    # "It is usually found at 8' pitch, occasionally at 16', and rarely at 4'." Audsley,
    # Organ-Stops and Their Artistic Registration (1921,
    # https://archive.org/download/cu31924086010331/cu31924086010331_djvu.txt): "The harmonic
    # upper partial tones of the Clarinet are those proper to a covered organ-pipe" and "the
    # Clarinet of the Organ should be carried, in all cases, throughout the manual compass".
    # Range: the manual, C2-C7, at 8'.
    # Sourced: the closed cylindrical resonator's odd harmonics (CLOSED_REED_LEVELS), the 8'
    # footage and the manual. Sound design: the table's slope (REED_STOP_LEVELS') and chiff,
    # copied from pipe organ reed
    CatalogEntry(
        'organ clarinet',
        "Clarinet 8'",
        Family.ORGANS,
        'C2',
        'C7',
        partial(_pipe_stop, CLOSED_REED_LEVELS, chiff=0.0),
    ),
    # The stopped diapason: Audsley, The Organ of the Twentieth Century (1919,
    # https://archive.org/download/organoftwentieth00audsuoft/organoftwentieth00audsuoft_djvu.txt):
    # covered wooden pipes "yield tones in which the second upper partial, or twelfth, of the
    # prime tone is present in a more or less pronounced degree", "With wind of still higher
    # pressure these pipes also give the fourth upper partial tone, or higher major third.
    # Covered pipes cannot give the uneven upper partial tones, such as the first or octave and
    # the third or super-octave, etc." and "The most important covered wood stops are the
    # STOPPED DIAPASON, BOURDON, DOPPELFLOTE, LIEBLICHGEDECKT, and QUINTATEN." Audsley counts
    # upper partials from the octave: the twelfth and the major third are harmonics 3 and 5, the
    # octave and super-octave harmonics 2 and 4 (STOPPED_FLUTE_LEVELS). Footage: the Encyclopedia
    # of Organ Stops (http://www.organstops.org/s/StoppedDiapason.html): "The name denotes a
    # stopped flute of 8' pitch, usually made of wood"; Audsley, Organ-Stops and Their Artistic
    # Registration (1921, https://archive.org/download/cu31924086010331/cu31924086010331_djvu.txt):
    # "A covered labial stop, of 8 ft. pitch in the manual divisions". Range: the manual, C2-C7,
    # at 8'.
    # Sourced: the missing even harmonics, the 8' footage and the manual. Sound design: the odd
    # harmonics' levels and chiff, copied from pipe organ flute
    CatalogEntry(
        'stopped diapason',
        "Stopped diapason 8'",
        Family.ORGANS,
        'C2',
        'C7',
        partial(_pipe_stop, STOPPED_FLUTE_LEVELS, chiff=0.02),
    ),
)

ORGANS: Final[tuple[CatalogEntry, ...]] = _ORGAN_BUILDS + ORGAN_SOUND_ALIKES
