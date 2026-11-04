"""Percussion: tuned (mallets, bells, pans, timpani, gamelan) and untuned (drums, cymbals).

Tuned percussion's partials are not harmonics. A free bar (glockenspiel) rings at 1 : 2.76 :
5.40 : 8.93 of its fundamental; marimba and vibraphone bars are cut so the first overtone is
the fourth harmonic and the xylophone's the third; a tubular bell's and a carillon bell's
partials (hum, prime, tierce and nominal; the weak quint is left out) give the bell's
minor-third colour; a tubular
bell's struck note is heard an octave below its fourth mode, which with the fifth and sixth
rings near 2 : 3 : 4 of that note; kalimba and music-box tines are clamped bars, ringing at 1 :
6.27 : 17.55, with no harmonics between; steel pans
and handpans are tuned to the octave and twelfth; a timpani's head favours 1 : 1.5 : 2 (Rossing,
*Science of Percussion Instruments*; Fletcher and Rossing, *The Physics of Musical
Instruments*). Untuned percussion is fixed tones and filtered noise: its sounds do not follow the
note's pitch, so those entries have no range.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import Partial, Tone, blown, drum, struck

if TYPE_CHECKING:
    from glitchygames.audio.instrument import Instrument

# A gamelan key's or singing bowl's second partial (a measured ratio, not e)
SINGING_METAL_SECOND_PARTIAL: Final[float] = 2.71  # ruff: ignore[math-constant] - measured, not e

# --- Tuned percussion -----------------------------------------------------------------------


def _bar(  # ruff: ignore[too-many-arguments] - a struck bar's partials
    ratios: tuple[float, ...],
    levels: tuple[float, ...],
    *,
    ring_seconds: float,
    mallet: float = 0.05,
    mallet_low_pass: float = 3000.0,
    overtone_ring: float = 0.25,
) -> Instrument:
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
    _bar,
    FREE_BAR_RATIOS,
    (1.0, 0.45),
    ring_seconds=2.5,
    mallet=0.06,
    mallet_low_pass=8000.0,
    overtone_ring=0.5,
)
XYLOPHONE = partial(
    _bar,
    (1.0, 3.0),
    (1.0, 0.35),
    ring_seconds=0.6,
    mallet=0.1,
    mallet_low_pass=6000.0,
    overtone_ring=0.5,
)
MARIMBA = partial(
    _bar, (1.0, 4.0, 9.9), (1.0, 0.25, 0.06), ring_seconds=1.2, mallet=0.04, mallet_low_pass=2000.0
)
VIBRAPHONE = partial(
    _bar,
    (1.0, 4.0, 10.0),
    (1.0, 0.22, 0.05),
    ring_seconds=4.0,
    mallet=0.03,
    mallet_low_pass=3000.0,
    overtone_ring=0.15,
)
GAMELAN_METALLOPHONE = partial(
    _bar,
    (1.0, SINGING_METAL_SECOND_PARTIAL, 5.15),
    (1.0, 0.4, 0.15),
    ring_seconds=3.0,
    mallet=0.06,
    mallet_low_pass=4000.0,
    overtone_ring=0.4,
)
KETTLE_GONG = partial(
    _bar,
    (1.0, 1.52, 2.0),
    (1.0, 0.35, 0.25),
    ring_seconds=2.0,
    mallet=0.05,
    mallet_low_pass=3000.0,
    overtone_ring=0.6,
)
HARMONIC_PAN = partial(
    _bar,
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


def _sustained_glass() -> Instrument:
    return blown((1.0, 0.04, 0.02), attack=0.25, release=0.6, chorus_cents=2.0)


TUNED_PERCUSSION: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry('glockenspiel', 'Glockenspiel', Family.TUNED_PERCUSSION, 'G5', 'C8', GLOCKENSPIEL),
    CatalogEntry(
        'crotales',
        'Crotales',
        Family.TUNED_PERCUSSION,
        'C6',
        'C8',
        partial(
            _bar,
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
            _bar,
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
            _bar,
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
            _bar,
            (1.0, 2.0, 3.0),
            (1.0, 0.4, 0.3),
            ring_seconds=3.0,
            mallet=0.03,
            mallet_low_pass=1500.0,
            overtone_ring=0.6,
        ),
    ),
    CatalogEntry(
        'kalimba',
        'Kalimba',
        Family.TUNED_PERCUSSION,
        'C4',
        'E6',
        partial(
            _bar,
            TINE_RATIOS,
            (1.0, 0.15),
            ring_seconds=1.5,
            mallet=0.08,
            mallet_low_pass=5000.0,
        ),
    ),
    CatalogEntry(
        'mbira',
        'Mbira',
        Family.TUNED_PERCUSSION,
        'G2',
        'D5',
        partial(
            _bar,
            TINE_RATIOS,
            (1.0, 0.2),
            ring_seconds=1.5,
            mallet=0.15,
            mallet_low_pass=6000.0,
        ),
    ),
    CatalogEntry(
        'music box',
        'Music box',
        Family.TUNED_PERCUSSION,
        'C4',
        'C7',
        partial(
            _bar,
            TINE_RATIOS,
            (1.0, 0.2),
            ring_seconds=1.2,
            mallet=0.03,
            mallet_low_pass=8000.0,
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
            _bar,
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
            _bar,
            (1.0, SINGING_METAL_SECOND_PARTIAL, 5.15),
            (1.0, 0.5, 0.2),
            ring_seconds=8.0,
            mallet=0.02,
            mallet_low_pass=2000.0,
            overtone_ring=0.6,
        ),
    ),
    CatalogEntry(
        'glass harmonica', 'Glass harmonica', Family.TUNED_PERCUSSION, 'G3', 'C6', _sustained_glass
    ),
    CatalogEntry(
        'tabla dayan',
        'Tabla (dayan)',
        Family.TUNED_PERCUSSION,
        'C4',
        'D5',
        partial(
            _bar,
            (1.0, 2.0, 3.0),
            (1.0, 0.5, 0.35),
            ring_seconds=0.6,
            mallet=0.15,
            mallet_low_pass=4000.0,
            overtone_ring=0.6,
        ),
    ),
)

# --- Drums and untuned percussion -----------------------------------------------------------


def _tom(hertz: float) -> Instrument:
    return drum(
        tones=(Tone(hertz=hertz, glide_to=hertz * 0.82, glide_seconds=0.15, ring_seconds=0.5),),
        noise=0.15,
        noise_ring_seconds=0.05,
        noise_low_pass=4000.0,
        tail=0.5,
    )


def _hand_drum(hertz: float, *, ring_seconds: float, slap: float = 0.15) -> Instrument:
    return drum(
        tones=(
            Tone(hertz=hertz, glide_to=hertz * 0.95, glide_seconds=0.05, ring_seconds=ring_seconds),
        ),
        noise=slap,
        noise_ring_seconds=0.03,
        noise_low_pass=6000.0,
        tail=ring_seconds,
    )


def _metal(
    frequencies: tuple[float, ...],
    *,
    ring_seconds: float,
    noise: float = 0.0,
    wave: str = 'sine',
    noise_high_pass: float | None = None,
) -> Instrument:
    return drum(
        tones=tuple(
            Tone(hertz=hertz, ring_seconds=ring_seconds, level=0.6, wave=wave)
            for hertz in frequencies
        ),
        noise=noise,
        noise_ring_seconds=ring_seconds / 2.0,
        noise_high_pass=noise_high_pass,
        tail=ring_seconds,
    )


def _cymbal(
    *, ring_seconds: float, high_pass: float, drive: float = 0.0, attack: float = 0.0
) -> Instrument:
    return drum(
        noise=1.0,
        noise_ring_seconds=ring_seconds,
        noise_high_pass=high_pass,
        tail=ring_seconds,
        drive=drive,
        attack=attack,
    )


def _shaker(*, ring_seconds: float, high_pass: float, attack: float = 0.01) -> Instrument:
    return drum(
        noise=1.0,
        noise_ring_seconds=ring_seconds,
        noise_high_pass=high_pass,
        tail=ring_seconds,
        attack=attack,
    )


DRUMS_AND_PERCUSSION: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'kick drum',
        'Kick drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=110.0, glide_to=45.0, glide_seconds=0.07, ring_seconds=0.45),),
            noise=0.2,
            noise_ring_seconds=0.01,
            noise_low_pass=3000.0,
            tail=0.4,
        ),
    ),
    CatalogEntry(
        'electronic kick',
        'Electronic kick (808-style)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=65.0, glide_to=42.0, glide_seconds=0.12, ring_seconds=1.2),),
            tail=1.0,
        ),
    ),
    CatalogEntry(
        'orchestral bass drum',
        'Orchestral bass drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=55.0, glide_to=48.0, glide_seconds=0.2, ring_seconds=1.8),),
            noise=0.25,
            noise_ring_seconds=0.4,
            noise_low_pass=500.0,
            tail=1.5,
        ),
    ),
    CatalogEntry(
        'snare drum',
        'Snare drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=190.0, ring_seconds=0.1),),
            noise=0.9,
            noise_ring_seconds=0.2,
            noise_high_pass=1500.0,
            tail=0.25,
        ),
    ),
    CatalogEntry(
        'snare rimshot',
        'Snare rimshot',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=220.0, ring_seconds=0.08),
                Tone(hertz=1700.0, ring_seconds=0.03, level=0.6),
            ),
            noise=0.9,
            noise_ring_seconds=0.18,
            noise_high_pass=2000.0,
            tail=0.25,
            drive=1.5,
        ),
    ),
    CatalogEntry(
        'snare brush',
        'Snare (brush swish)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_shaker, ring_seconds=0.35, high_pass=2500.0, attack=0.06),
    ),
    CatalogEntry(
        'electronic snare',
        'Electronic snare',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=180.0, ring_seconds=0.12),
                Tone(hertz=330.0, ring_seconds=0.08, level=0.5),
            ),
            noise=0.7,
            noise_ring_seconds=0.18,
            noise_high_pass=3000.0,
            tail=0.25,
        ),
    ),
    CatalogEntry(
        'high tom', 'High tom', Family.DRUMS_AND_PERCUSSION, None, None, partial(_tom, 210.0)
    ),
    CatalogEntry(
        'mid tom', 'Mid tom', Family.DRUMS_AND_PERCUSSION, None, None, partial(_tom, 160.0)
    ),
    CatalogEntry(
        'low tom', 'Low tom', Family.DRUMS_AND_PERCUSSION, None, None, partial(_tom, 120.0)
    ),
    CatalogEntry(
        'floor tom', 'Floor tom', Family.DRUMS_AND_PERCUSSION, None, None, partial(_tom, 88.0)
    ),
    CatalogEntry(
        'closed hi hat',
        'Closed hi-hat',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=0.05, high_pass=7000.0),
    ),
    CatalogEntry(
        'pedal hi hat',
        'Pedal hi-hat',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=0.08, high_pass=5000.0, attack=0.004),
    ),
    CatalogEntry(
        'open hi hat',
        'Open hi-hat',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=0.6, high_pass=6500.0),
    ),
    CatalogEntry(
        'crash cymbal',
        'Crash cymbal',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=2.5, high_pass=3000.0),
    ),
    CatalogEntry(
        'ride cymbal',
        'Ride cymbal',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            _metal, (2600.0, 3720.0, 5310.0), ring_seconds=1.8, noise=0.5, noise_high_pass=5000.0
        ),
    ),
    CatalogEntry(
        'ride bell',
        'Ride cymbal bell',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            _metal, (880.0, 2390.0, 3410.0), ring_seconds=1.5, noise=0.15, noise_high_pass=6000.0
        ),
    ),
    CatalogEntry(
        'splash cymbal',
        'Splash cymbal',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=0.8, high_pass=4500.0),
    ),
    CatalogEntry(
        'china cymbal',
        'China cymbal',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=1.8, high_pass=2000.0, drive=3.0),
    ),
    CatalogEntry(
        'suspended cymbal roll',
        'Suspended cymbal (swell)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=3.0, high_pass=3000.0, attack=1.0),
    ),
    CatalogEntry(
        'crash cymbals pair',
        'Clash cymbals (pair)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_cymbal, ring_seconds=3.5, high_pass=2000.0, drive=1.0),
    ),
    CatalogEntry(
        'tam tam',
        'Tam-tam',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=72.0, ring_seconds=6.0),
                Tone(hertz=133.0, ring_seconds=5.0, level=0.5),
            ),
            noise=0.6,
            noise_ring_seconds=5.0,
            noise_low_pass=2500.0,
            tail=6.0,
            attack=0.15,
        ),
    ),
    CatalogEntry(
        'tambourine',
        'Tambourine',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (5400.0, 7300.0), ring_seconds=0.25, noise=0.8, noise_high_pass=6000.0),
    ),
    CatalogEntry(
        'triangle',
        'Triangle',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (4200.0, 7580.0, 10500.0), ring_seconds=2.5),
    ),
    CatalogEntry(
        'cowbell',
        'Cowbell',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (540.0, 800.0), ring_seconds=0.35, wave='square'),
    ),
    CatalogEntry(
        'high agogo',
        'Agogô (high)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (930.0, 2510.0), ring_seconds=0.5),
    ),
    CatalogEntry(
        'low agogo',
        'Agogô (low)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (660.0, 1780.0), ring_seconds=0.5),
    ),
    CatalogEntry(
        'finger cymbals',
        'Finger cymbals',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_metal, (3700.0, 5300.0, 8900.0), ring_seconds=2.0),
    ),
    CatalogEntry(
        'wind gong',
        'Wind gong',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=150.0, ring_seconds=3.0),),
            noise=0.8,
            noise_ring_seconds=3.0,
            noise_high_pass=1200.0,
            tail=3.0,
            attack=0.05,
        ),
    ),
    CatalogEntry(
        'claves',
        'Claves',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(drum, tones=(Tone(hertz=2500.0, ring_seconds=0.06),), tail=0.08),
    ),
    CatalogEntry(
        'woodblock',
        'Woodblock',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=1050.0, ring_seconds=0.07),
                Tone(hertz=1680.0, ring_seconds=0.04, level=0.4),
            ),
            noise=0.2,
            noise_ring_seconds=0.01,
            noise_high_pass=2000.0,
            tail=0.1,
        ),
    ),
    CatalogEntry(
        'temple block',
        'Temple block',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(hertz=620.0, ring_seconds=0.15),
                Tone(hertz=1430.0, ring_seconds=0.06, level=0.3),
            ),
            noise=0.15,
            noise_ring_seconds=0.01,
            noise_high_pass=2000.0,
            tail=0.2,
        ),
    ),
    CatalogEntry(
        'castanets',
        'Castanets',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=3100.0, ring_seconds=0.02),),
            noise=0.7,
            noise_ring_seconds=0.02,
            noise_high_pass=2500.0,
            tail=0.05,
        ),
    ),
    CatalogEntry(
        'shaker',
        'Shaker',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_shaker, ring_seconds=0.08, high_pass=5000.0),
    ),
    CatalogEntry(
        'maracas',
        'Maracas',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_shaker, ring_seconds=0.06, high_pass=4000.0, attack=0.005),
    ),
    CatalogEntry(
        'cabasa',
        'Cabasa',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_shaker, ring_seconds=0.1, high_pass=6000.0, attack=0.02),
    ),
    CatalogEntry(
        'guiro',
        'Güiro',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_shaker, ring_seconds=0.25, high_pass=2500.0, attack=0.15),
    ),
    CatalogEntry(
        'hand clap',
        'Hand clap',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(drum, noise=1.0, noise_ring_seconds=0.12, noise_low_pass=2500.0, tail=0.15),
    ),
    CatalogEntry(
        'finger snap',
        'Finger snap',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=2200.0, ring_seconds=0.02, level=0.5),),
            noise=1.0,
            noise_ring_seconds=0.03,
            noise_high_pass=2000.0,
            tail=0.05,
        ),
    ),
    CatalogEntry(
        'high bongo',
        'Bongo (high)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 420.0, ring_seconds=0.15),
    ),
    CatalogEntry(
        'low bongo',
        'Bongo (low)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 310.0, ring_seconds=0.18),
    ),
    CatalogEntry(
        'conga',
        'Conga (open)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 215.0, ring_seconds=0.35),
    ),
    CatalogEntry(
        'tumba',
        'Tumba',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 165.0, ring_seconds=0.4),
    ),
    CatalogEntry(
        'conga slap',
        'Conga (slap)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 330.0, ring_seconds=0.06, slap=0.8),
    ),
    CatalogEntry(
        'high timbale',
        'Timbale (high)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 480.0, ring_seconds=0.4, slap=0.5),
    ),
    CatalogEntry(
        'low timbale',
        'Timbale (low)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 350.0, ring_seconds=0.45, slap=0.5),
    ),
    CatalogEntry(
        'djembe bass',
        'Djembe (bass)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 75.0, ring_seconds=0.4, slap=0.1),
    ),
    CatalogEntry(
        'djembe tone',
        'Djembe (tone)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 330.0, ring_seconds=0.2),
    ),
    CatalogEntry(
        'djembe slap',
        'Djembe (slap)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 520.0, ring_seconds=0.05, slap=0.9),
    ),
    CatalogEntry(
        'cajon bass',
        'Cajón (bass)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 85.0, ring_seconds=0.25, slap=0.2),
    ),
    CatalogEntry(
        'cajon slap',
        'Cajón (slap)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=260.0, ring_seconds=0.05),),
            noise=0.9,
            noise_ring_seconds=0.12,
            noise_high_pass=1800.0,
            tail=0.15,
        ),
    ),
    CatalogEntry(
        'tabla bayan',
        'Tabla (bayan)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=95.0, glide_to=125.0, glide_seconds=0.25, ring_seconds=0.6),),
            tail=0.5,
        ),
    ),
    CatalogEntry(
        'taiko',
        'Taiko (ōdaiko)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=70.0, glide_to=56.0, glide_seconds=0.2, ring_seconds=1.2),),
            noise=0.35,
            noise_ring_seconds=0.08,
            noise_low_pass=1500.0,
            tail=1.0,
        ),
    ),
    CatalogEntry(
        'bodhran',
        'Bodhrán',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=95.0, glide_to=85.0, glide_seconds=0.1, ring_seconds=0.35),),
            noise=0.3,
            noise_ring_seconds=0.04,
            noise_low_pass=2500.0,
            tail=0.3,
        ),
    ),
    CatalogEntry(
        'frame drum',
        'Frame drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 130.0, ring_seconds=0.5, slap=0.2),
    ),
    CatalogEntry(
        'darbuka doum',
        'Darbuka (doum)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 140.0, ring_seconds=0.4, slap=0.1),
    ),
    CatalogEntry(
        'darbuka tek',
        'Darbuka (tek)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(Tone(hertz=750.0, ring_seconds=0.04),),
            noise=0.8,
            noise_ring_seconds=0.04,
            noise_high_pass=2500.0,
            tail=0.08,
        ),
    ),
    CatalogEntry(
        'surdo',
        'Surdo',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(_hand_drum, 62.0, ring_seconds=0.9, slap=0.1),
    ),
    CatalogEntry(
        'cuica',
        'Cuíca',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum,
            tones=(
                Tone(
                    hertz=420.0,
                    glide_to=780.0,
                    glide_seconds=0.12,
                    ring_seconds=0.2,
                    wave='triangle',
                ),
            ),
            tail=0.15,
        ),
    ),
    CatalogEntry(
        'vibraslap',
        'Vibraslap',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            _metal,
            (1150.0, 2480.0),
            ring_seconds=0.8,
            noise=0.5,
            wave='square',
            noise_high_pass=3000.0,
        ),
    ),
    CatalogEntry(
        'whip',
        'Whip (slapstick)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        partial(
            drum, noise=1.0, noise_ring_seconds=0.03, noise_high_pass=1000.0, tail=0.05, drive=2.0
        ),
    ),
)
