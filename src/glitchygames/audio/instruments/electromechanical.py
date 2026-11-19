"""Electromechanical instruments: electric pianos, Clavinet, Pianet and tonewheel organs.

The tonewheel organ's drawbar registrations (``Harmonics.drawbars``) and percussion, a decaying
second or third harmonic, are here with the electric pianos, the Clavinet and the Pianet, which
read a mechanical vibration electrically. Ranges are each instrument's keyboard. The keyboards are
in ``keyboards.py``.
"""

from __future__ import annotations

import math
from functools import partial
from typing import Final

from glitchygames.audio.instrument import Instrument, Source
from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import (
    Partial,
    drawbar_organ,
    envelope,
    falling_series,
    plucked,
    plucked_series,
    struck,
)
from glitchygames.audio.waves import Harmonics, Wave

# --- Electromechanical ----------------------------------------------------------------------

# Electromechanical instruments (Hornbostel-Sachs 51 and 52): a mechanical vibration (a tine, a
# reed, a string, a spinning tonewheel) picked up electrically, so the sound starts as a
# mechanical vibration and the electronics only read and amplify it. The Hornbostel-Sachs
# electrophone list is at https://en.wikipedia.org/wiki/Electrophone ("51=electrically actuated
# acoustic instruments", "52=electrically amplified acoustic instruments"; it calls the Hammond
# organ "an electromechanical instrument, as it used both mechanical elements and electronic
# parts"). The eleven moved entries keep their builders and their ranges unchanged; each cites its
# sources below, as the audit sheet plans/data/instrument-audit/batch-2.tsv does.


def _tine_piano() -> Instrument:
    # A tine electric piano: a nearly pure tone with a bell-like partial on the attack
    return struck(
        (
            Partial(ratio=1.0, level=1.0, ring_seconds=3.0),
            Partial(ratio=2.0, level=0.25, ring_seconds=1.5),
            Partial(ratio=7.1, level=0.3, ring_seconds=0.25),
        ),
        release=0.35,
        mallet=0.02,
        mallet_low_pass=2000.0,
    )


def _reed_piano() -> Instrument:
    # A reed electric piano: a struck steel reed read by an electrostatic pickup, every harmonic
    # (close to a sawtooth) and driven, as the pickup's nonlinearity gives its bark
    return plucked(
        falling_series(count=16, decibels_per_octave=6.0),
        ring_seconds=2.0,
        release=0.2,
        drive=1.5,
        low_pass=4000.0,
    )


def _pianet() -> Instrument:
    # A reed released by a pad: harmonics 1 to 4, each higher one ringing shorter
    return struck(
        (
            Partial(ratio=1.0, level=1.0, ring_seconds=1.2),
            Partial(ratio=2.0, level=0.5, ring_seconds=0.5),
            Partial(ratio=3.0, level=0.35, ring_seconds=0.2),
            Partial(ratio=4.0, level=0.25, ring_seconds=0.08),
        ),
        release=0.15,
        low_pass=3000.0,
    )


def _clavinet() -> Instrument:
    return plucked(
        plucked_series(count=28, decibels_per_octave=2.0, pluck_position=0.06),
        ring_seconds=1.0,
        release=0.08,
        high_pass=150.0,
        drive=0.8,
    )


def _tonewheel_with_percussion(setting: str, *, percussion_harmonic: float) -> Instrument:
    # The percussion: a second or third harmonic that decays while the key is held
    body = Wave.from_harmonics(Harmonics.drawbars(setting))
    return Instrument(
        sources={
            'drawbars': Source(body),
            'percussion': Source(
                'sine',
                semitones=12.0 * math.log2(percussion_harmonic),
                level=0.6,
                envelope=envelope(attack=0.001, decay=0.4, sustain=0.0, release=0.05),
            ),
        },
        envelope=envelope(attack=0.004, release=0.05, curve='linear'),
        normalize=True,
    )


ELECTROMECHANICAL: Final[tuple[CatalogEntry, ...]] = (
    # Range: kept from the catalog: no source gives the ends
    # (https://en.wikipedia.org/wiki/Fender_Rhodes gives "54, 73 or 88 keys" and no note names
    # for them; E1 - E7 is 73 keys, and nothing fetched shows it wrong)
    # Sound: https://en.wikipedia.org/wiki/Fender_Rhodes ("the hammers strike thin metal tines,
    # which vibrate next to an electromagnetic pickup"; "Vibrating tines produce a mellower
    # timbre"; tine and pickup close together give "a characteristic "bell" sound"); the build is
    # unchanged from before the move
    CatalogEntry(
        'tine electric piano',
        'Electric piano (tine)',
        Family.ELECTROMECHANICAL,
        'E1',
        'E7',
        _tine_piano,
    ),
    # Range: https://en.wikipedia.org/wiki/Wurlitzer_electric_piano ("Most Wurlitzer pianos are
    # 64-note instruments whose keyboard range is from A an octave above the lowest note of a
    # standard 88-note piano to the C an octave below its top note": A1 - C7)
    # Sound: the same page ("striking a metal reed with a felt hammer", an electrostatic pickup;
    # "closer to a sawtooth wave"; played hard, a tone "usually described as a "bark""); the build
    # is unchanged from before the move
    CatalogEntry(
        'reed electric piano',
        'Electric piano (reed)',
        Family.ELECTROMECHANICAL,
        'A1',
        'C7',
        _reed_piano,
    ),
    # Range: https://en.wikipedia.org/wiki/Hohner_Clavinet ("Most models have 60 keys ranging from
    # F1 to E6")
    # Sound: the same page ("a harp of 60 tensioned steel strings placed diagonally below the key
    # surface"); the build is unchanged from before the move
    CatalogEntry('clavinet', 'Clavinet', Family.ELECTROMECHANICAL, 'F1', 'E6', _clavinet),
    # The seven tonewheel organ entries below share these sources.
    # Range: kept from the catalog: no source gives the ends
    # (https://en.wikipedia.org/wiki/Hammond_organ says "Most Hammond organs have two 61-note
    # (five-octave) keyboards" and names no notes; C2 - C7 is a 61-note manual at 8' pitch, and
    # nothing fetched shows it wrong)
    # Sound: the same page (a tonewheel turns "near an electromagnetic pickup", giving "a signal
    # similar to a sine wave"; mixing the drawbars makes it "a type of additive synthesis"; the
    # percussion "plays a decaying second- or third-harmonic overtone when a key is pressed"); the
    # builds are unchanged from before the move
    CatalogEntry(
        'tonewheel organ jazz',
        'Tonewheel organ (888000000)',
        Family.ELECTROMECHANICAL,
        'C2',
        'C7',
        partial(drawbar_organ, '888000000'),
    ),
    CatalogEntry(
        'tonewheel organ full',
        'Tonewheel organ (888888888)',
        Family.ELECTROMECHANICAL,
        'C2',
        'C7',
        partial(drawbar_organ, '888888888'),
    ),
    CatalogEntry(
        'tonewheel organ ballad',
        'Tonewheel organ (808000000)',
        Family.ELECTROMECHANICAL,
        'C2',
        'C7',
        partial(drawbar_organ, '808000000'),
    ),
    CatalogEntry(
        'tonewheel organ rock',
        'Tonewheel organ (888800000)',
        Family.ELECTROMECHANICAL,
        'C2',
        'C7',
        partial(drawbar_organ, '888800000'),
    ),
    CatalogEntry(
        'tonewheel organ gospel',
        'Tonewheel organ (868000004)',
        Family.ELECTROMECHANICAL,
        'C2',
        'C7',
        partial(drawbar_organ, '868000004'),
    ),
    CatalogEntry(
        'tonewheel organ percussion second',
        'Tonewheel organ, second-harmonic percussion',
        Family.ELECTROMECHANICAL,
        'C2',
        'C7',
        partial(_tonewheel_with_percussion, '808000000', percussion_harmonic=2.0),
    ),
    CatalogEntry(
        'tonewheel organ percussion third',
        'Tonewheel organ, third-harmonic percussion',
        Family.ELECTROMECHANICAL,
        'C2',
        'C7',
        partial(_tonewheel_with_percussion, '888000000', percussion_harmonic=3.0),
    ),
    # Range: https://en.wikipedia.org/wiki/Hohner_Pianet ("It had 61 keys ranging from F1 to F6";
    # "Later models had 60 keys, missing the top F": the original compass is used)
    # Sound: https://en.wikipedia.org/wiki/Hohner_Pianet ("This pad adheres to the reed when at
    # rest, and lifts and releases the reed causing it to vibrate when the key is depressed": the
    # reed is released, not hammered; "The resulting sound has a complex mixture of harmonics when
    # the reed is first struck, which later reduces to a cleaner sustained tone")
    # Built with struck so each harmonic dies away at its own rate: the higher a harmonic, the
    # shorter its ring, so the strike is bright and the tone settles toward the fundamental. A
    # reed, not a tine, so its partials are harmonics, with no tine piano's 7.1x bell partial.
    # The levels, the 1.2 s to 0.08 s rings, the 0.15 s release and the 3 kHz low pass are to be
    # tuned by ear (the sources give no numbers). Unlike the reed electric piano it has no drive
    # (no hammer bark) and a shorter ring
    CatalogEntry(
        'hohner pianet',
        'Hohner Pianet',
        Family.ELECTROMECHANICAL,
        'F1',
        'F6',
        _pianet,
    ),
)
