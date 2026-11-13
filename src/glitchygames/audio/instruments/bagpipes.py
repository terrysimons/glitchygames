"""Bagpipes: reed chanters sounded from a bag, over fixed drones or none.

A bagpipe is a set of reed pipes sounded from a flexible air reservoir, the bag, blown by mouth or
by bellows: Hornbostel-Sachs' -62 suffix, "with flexible air reservoir". Its chanter is one pipe
or two, a double reed (an oboe, 422.1) or a single reed (a clarinet, 422.2), conical or
cylindrical. A bagpipe's chanter sounds over fixed drones, and ranges are sounding pitch. The
family's sound-alikes, listed instruments that share another entry's build, are in
``bagpipe_sound_alikes.py``. The other reed families are in the sibling modules ``winds.py`` and
``double_reeds.py``.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.bagpipe_sound_alikes import BAGPIPE_SOUND_ALIKES
from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import blown, wave_from_levels, with_drones

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

# The Highland and uilleann timbres are scripts/make_pipes.py's, tuned there by ear
HIGHLAND_LEVELS: Final[tuple[float, ...]] = (
    1.0,
    0.95,
    0.85,
    0.8,
    0.75,
    0.65,
    0.55,
    0.5,
    0.42,
    0.36,
    0.3,
    0.25,
)
DRONE_LEVELS: Final[tuple[float, ...]] = (1.0, 0.7, 0.55, 0.4, 0.3, 0.22, 0.15, 0.1)
SWEET_CHANTER_LEVELS: Final[tuple[float, ...]] = (1.0, 0.55, 0.4, 0.26, 0.17, 0.1, 0.06, 0.035)
SMOOTH_DRONE_LEVELS: Final[tuple[float, ...]] = (1.0, 0.3, 0.12, 0.05)
# A cylindrical single-reed chanter: SWEET_CHANTER_LEVELS' odd harmonics with the even ones silent.
# The odd-harmonics-only shape is sound design, from a closed cylinder favouring odd harmonics;
# the bore itself is sourced (Alban Faust, a maker, https://www.albanfaust.se/en/the-instrumentmaker/:
# "a single reed which sits on a cylindrically drilled chanter")
CYLINDRICAL_CHANTER_LEVELS: Final[tuple[float, ...]] = (1.0, 0.0, 0.4, 0.0, 0.17, 0.0, 0.06, 0.0)


def _bagpipe(  # ruff: ignore[too-many-arguments] - a chanter's traits and its drones
    *,
    chanter_levels: tuple[float, ...],
    drones: tuple[tuple[float, float], ...],
    drone_levels: tuple[float, ...],
    low_pass: float,
    drive: float,
    breath: float,
    attack: float = 0.006,
    sustain: float = 1.0,
) -> Instrument:
    chanter = blown(
        chanter_levels,
        attack=attack,
        decay=0.04 if sustain < 1.0 else 0.0,
        sustain=sustain,
        release=0.03,
        breath=breath,
        breath_low_pass=4500.0,
        low_pass=low_pass,
        drive=drive,
    )
    return with_drones(chanter, drones=drones, drone_wave=wave_from_levels(drone_levels))


_BAGPIPE_BUILDS: Final[tuple[CatalogEntry, ...]] = (
    # Chanter A near 480 Hz (pipers tune sharp); tenor drones an octave below, bass two
    CatalogEntry(
        'highland bagpipe',
        'Great Highland bagpipe',
        Family.BAGPIPES,
        'Ab4',
        'Bb5',
        partial(
            _bagpipe,
            chanter_levels=HIGHLAND_LEVELS,
            drones=((240.0, 0.45), (120.0, 0.55)),
            drone_levels=DRONE_LEVELS,
            low_pass=6500.0,
            drive=1.25,
            breath=0.012,
        ),
    ),
    CatalogEntry(
        'uilleann pipes',
        'Uilleann pipes',
        Family.BAGPIPES,
        'D4',
        'E6',
        partial(
            _bagpipe,
            chanter_levels=SWEET_CHANTER_LEVELS,
            drones=((146.83, 0.25), (73.42, 0.3)),
            drone_levels=SMOOTH_DRONE_LEVELS,
            low_pass=3500.0,
            drive=0.0,
            breath=0.015,
            attack=0.012,
            sustain=0.85,
        ),
    ),
    CatalogEntry(
        'scottish smallpipes',
        'Scottish smallpipes in A',
        Family.BAGPIPES,
        'G4',
        'A5',
        partial(
            _bagpipe,
            chanter_levels=SWEET_CHANTER_LEVELS,
            drones=((220.0, 0.3), (110.0, 0.35)),
            drone_levels=SMOOTH_DRONE_LEVELS,
            low_pass=4000.0,
            drive=0.3,
            breath=0.01,
        ),
    ),
    CatalogEntry(
        'border pipes',
        'Border pipes',
        Family.BAGPIPES,
        'G4',
        'A5',
        partial(
            _bagpipe,
            chanter_levels=HIGHLAND_LEVELS,
            drones=((220.0, 0.4), (110.0, 0.45)),
            drone_levels=DRONE_LEVELS,
            low_pass=5000.0,
            drive=0.8,
            breath=0.012,
        ),
    ),
    # Closed-ended: notes are detached, so the chanter drops between them
    CatalogEntry(
        'northumbrian smallpipes',
        'Northumbrian smallpipes',
        Family.BAGPIPES,
        'G4',
        'A5',
        partial(
            _bagpipe,
            chanter_levels=SWEET_CHANTER_LEVELS,
            drones=((196.0, 0.25), (98.0, 0.3)),
            drone_levels=SMOOTH_DRONE_LEVELS,
            low_pass=4500.0,
            drive=0.0,
            breath=0.008,
            attack=0.008,
            sustain=0.6,
        ),
    ),
    CatalogEntry(
        'galician gaita',
        'Galician gaita in D',
        Family.BAGPIPES,
        'C#5',
        'E6',
        partial(
            _bagpipe,
            chanter_levels=HIGHLAND_LEVELS,
            drones=((293.66, 0.3), (146.83, 0.4)),
            drone_levels=DRONE_LEVELS,
            low_pass=7000.0,
            drive=1.0,
            breath=0.012,
        ),
    ),
    CatalogEntry(
        'bulgarian gaida',
        'Bulgarian gaida',
        Family.BAGPIPES,
        'F#4',
        'A5',
        partial(
            _bagpipe,
            chanter_levels=HIGHLAND_LEVELS,
            drones=((196.0, 0.5),),
            drone_levels=DRONE_LEVELS,
            low_pass=6000.0,
            drive=1.0,
            breath=0.012,
        ),
    ),
    CatalogEntry(
        'musette de cour',
        'Musette de cour',
        Family.BAGPIPES,
        'F4',
        'D6',
        partial(
            _bagpipe,
            chanter_levels=SWEET_CHANTER_LEVELS,
            drones=((174.61, 0.2), (87.31, 0.25)),
            drone_levels=SMOOTH_DRONE_LEVELS,
            low_pass=3500.0,
            drive=0.0,
            breath=0.008,
        ),
    ),
    # --- Batch 12's bagpipes, in the order of plans/data/instrument-audit/batch-12.tsv
    # Alban Faust, a maker (https://www.albanfaust.se/en/the-instrumentmaker/): "The Swedish
    # bagpipes is a so-called clarinet-instrument, as the sound is produced through a single reed
    # which sits on a cylindrically drilled chanter. Traditionally it is a mouth blown instrument
    # with one short drone (high tuned) which is identical to the lowest tone on the chanter (6
    # fingering)." Range and drone: Leif Eriksson, a maker writing of his own bagpipes
    # (https://tongang.se/leif/leif/bagpipes_2.html): "The normal key for the Swedish bagpipe is
    # a', the lowest tone being e', and the highest e'', with a', in the middle." and "The drone
    # is normally tuned to the e' of the chanter." e' is E4 and e'' is E5 (Helmholtz notation), so
    # the one drone sounds E4, 329.63 Hz equal-tempered at A4 = 440 Hz.
    # Sourced: the cylindrical single-reed chanter (CYLINDRICAL_CHANTER_LEVELS), the range E4-E5
    # and the one drone at E4. Sound design, copied unchanged from scottish smallpipes (the nearest
    # in kind, a soft bagpipe; the Swedish bagpipes page,
    # https://en.wikipedia.org/wiki/Swedish_bagpipes: "The tone of the instrument is quite soft"):
    # the drone level 0.35 (that entry's lowest drone's), drone_levels, low_pass, drive, breath,
    # and the builder's default attack and sustain
    CatalogEntry(
        'sackpipa',
        'Säckpipa in A',
        Family.BAGPIPES,
        'E4',
        'E5',
        partial(
            _bagpipe,
            chanter_levels=CYLINDRICAL_CHANTER_LEVELS,
            drones=((329.63, 0.35),),
            drone_levels=SMOOTH_DRONE_LEVELS,
            low_pass=4000.0,
            drive=0.3,
            breath=0.01,
        ),
    ),
)

BAGPIPES: Final[tuple[CatalogEntry, ...]] = _BAGPIPE_BUILDS + BAGPIPE_SOUND_ALIKES
