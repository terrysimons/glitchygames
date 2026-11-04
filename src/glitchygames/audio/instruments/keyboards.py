"""Keyboards (pianos, harpsichords, electric pianos, celesta), organs and electronic instruments.

A piano string is struck by a hammer near a seventh of its length, so its seventh harmonic is
nearly gone; each note has two or three slightly detuned strings, whose beating is the piano's
shimmer. A harpsichord's quill plucks near the end (bright) and has a 4' octave rank. Organs are
drawbar registrations (``Harmonics.drawbars``) or pipe stops: a principal's every harmonic, a
flute stop's nearly pure tone, a reed stop's brassy one. The tonewheel organ's percussion is a
decaying second or third harmonic. Ranges are each instrument's keyboard; an organ's are its
keys at 8' pitch (a 61-note manual, C2-C7), and a 16' stop or drawbar sounds an octave lower.
"""

from __future__ import annotations

import math
from functools import partial
from typing import Final

from glitchygames.audio.instrument import Filter, Instrument, Source
from glitchygames.audio.instruments.catalog import CatalogEntry, Family
from glitchygames.audio.instruments.timbres import (
    Course,
    Partial,
    blown,
    drawbar_organ,
    envelope,
    falling_series,
    plucked,
    plucked_series,
    struck,
)
from glitchygames.audio.waves import Harmonics, Wave

# --- Keyboards ------------------------------------------------------------------------------


def _piano(
    *, ring_seconds: float, low_pass: float, cents: float, slope: float = 6.0, hammer: float = 0.03
) -> Instrument:
    return plucked(
        plucked_series(count=24, decibels_per_octave=slope, pluck_position=1.0 / 7.0),
        ring_seconds=ring_seconds,
        release=0.25,
        courses=(Course(cents=cents, level=0.8), Course(cents=-cents / 2.0, level=0.6)),
        pick=hammer,
        pick_high_pass=1000.0,
        low_pass=low_pass,
    )


def _harpsichord(*, low_pass: float, octave_rank: bool) -> Instrument:
    courses = (Course(semitones=12.0, cents=1.0, level=0.45),) if octave_rank else ()
    return plucked(
        plucked_series(count=28, decibels_per_octave=2.5, pluck_position=0.08),
        ring_seconds=2.0,
        release=0.12,
        courses=courses,
        pick=0.04,
        pick_high_pass=3000.0,
        low_pass=low_pass,
    )


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


def _clavinet() -> Instrument:
    return plucked(
        plucked_series(count=28, decibels_per_octave=2.0, pluck_position=0.06),
        ring_seconds=1.0,
        release=0.08,
        high_pass=150.0,
        drive=0.8,
    )


def _celesta(*, ring_seconds: float) -> Instrument:
    return struck(
        (
            Partial(ratio=1.0, level=1.0, ring_seconds=ring_seconds),
            Partial(ratio=4.0, level=0.2, ring_seconds=ring_seconds / 4.0),
        ),  # under Nyquist at C8
        release=ring_seconds / 2.0,
        mallet=0.02,
    )


def _toy_piano() -> Instrument:
    # Struck metal rods: inharmonic partials (a free bar's 1 : 2.76 : 5.40)
    return struck(
        (
            Partial(ratio=1.0, level=1.0, ring_seconds=1.2),
            Partial(ratio=2.76, level=0.5, ring_seconds=0.6),
            Partial(ratio=5.40, level=0.25, ring_seconds=0.3),
        ),
        release=0.6,
        mallet=0.05,
    )


KEYBOARDS: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry(
        'grand piano',
        'Grand piano',
        Family.KEYBOARDS,
        'A0',
        'C8',
        partial(_piano, ring_seconds=4.5, low_pass=6000.0, cents=1.5),
    ),
    CatalogEntry(
        'bright grand piano',
        'Bright grand piano',
        Family.KEYBOARDS,
        'A0',
        'C8',
        partial(_piano, ring_seconds=4.0, low_pass=9000.0, cents=1.5, slope=4.5, hammer=0.05),
    ),
    CatalogEntry(
        'upright piano',
        'Upright piano',
        Family.KEYBOARDS,
        'A0',
        'C8',
        partial(_piano, ring_seconds=3.0, low_pass=5000.0, cents=2.5),
    ),
    CatalogEntry(
        'honky tonk piano',
        'Honky-tonk piano',
        Family.KEYBOARDS,
        'A0',
        'C8',
        partial(_piano, ring_seconds=3.0, low_pass=6000.0, cents=16.0),
    ),
    CatalogEntry(
        'fortepiano',
        'Fortepiano',
        Family.KEYBOARDS,
        'F1',
        'F6',
        partial(_piano, ring_seconds=2.0, low_pass=5500.0, cents=2.0, slope=5.0),
    ),
    CatalogEntry(
        'harpsichord',
        "Harpsichord (8' + 4')",
        Family.KEYBOARDS,
        'F1',
        'F6',
        partial(_harpsichord, low_pass=9000.0, octave_rank=True),
    ),
    CatalogEntry(
        'harpsichord lute stop',
        'Harpsichord (lute stop)',
        Family.KEYBOARDS,
        'F1',
        'F6',
        partial(_harpsichord, low_pass=3500.0, octave_rank=False),
    ),
    CatalogEntry(
        'virginal',
        'Virginal',
        Family.KEYBOARDS,
        'C2',
        'C6',
        partial(_harpsichord, low_pass=7000.0, octave_rank=False),
    ),
    CatalogEntry(
        'clavichord',
        'Clavichord',
        Family.KEYBOARDS,
        'C2',
        'E6',
        partial(_piano, ring_seconds=1.5, low_pass=5000.0, cents=1.0, slope=4.0, hammer=0.0),
    ),
    CatalogEntry(
        'tine electric piano', 'Electric piano (tine)', Family.KEYBOARDS, 'E1', 'E7', _tine_piano
    ),
    CatalogEntry(
        'reed electric piano', 'Electric piano (reed)', Family.KEYBOARDS, 'A1', 'C7', _reed_piano
    ),
    CatalogEntry('clavinet', 'Clavinet', Family.KEYBOARDS, 'F1', 'E6', _clavinet),
    CatalogEntry(
        'celesta', 'Celesta', Family.KEYBOARDS, 'C4', 'C8', partial(_celesta, ring_seconds=1.5)
    ),
    CatalogEntry('toy piano', 'Toy piano', Family.KEYBOARDS, 'F3', 'F6', _toy_piano),
)

# --- Organs ---------------------------------------------------------------------------------


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


def _pipe_stop(levels: tuple[float, ...], *, chiff: float, release: float = 0.15) -> Instrument:
    return blown(levels, attack=0.04, release=release, breath=chiff, breath_low_pass=6000.0)


PRINCIPAL_LEVELS: Final[tuple[float, ...]] = falling_series(count=16, decibels_per_octave=6.5)
FLUTE_STOP_LEVELS: Final[tuple[float, ...]] = (1.0, 0.1, 0.12, 0.02, 0.02)
REED_STOP_LEVELS: Final[tuple[float, ...]] = falling_series(count=28, decibels_per_octave=2.5)
STRING_STOP_LEVELS: Final[tuple[float, ...]] = falling_series(count=28, decibels_per_octave=4.0)
CALLIOPE_LEVELS: Final[tuple[float, ...]] = (1.0, 0.25, 0.2, 0.05)

ORGANS: Final[tuple[CatalogEntry, ...]] = (
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
        'tonewheel organ jazz',
        'Tonewheel organ (888000000)',
        Family.ORGANS,
        'C2',
        'C7',
        partial(drawbar_organ, '888000000'),
    ),
    CatalogEntry(
        'tonewheel organ full',
        'Tonewheel organ (888888888)',
        Family.ORGANS,
        'C2',
        'C7',
        partial(drawbar_organ, '888888888'),
    ),
    CatalogEntry(
        'tonewheel organ ballad',
        'Tonewheel organ (808000000)',
        Family.ORGANS,
        'C2',
        'C7',
        partial(drawbar_organ, '808000000'),
    ),
    CatalogEntry(
        'tonewheel organ rock',
        'Tonewheel organ (888800000)',
        Family.ORGANS,
        'C2',
        'C7',
        partial(drawbar_organ, '888800000'),
    ),
    CatalogEntry(
        'tonewheel organ gospel',
        'Tonewheel organ (868000004)',
        Family.ORGANS,
        'C2',
        'C7',
        partial(drawbar_organ, '868000004'),
    ),
    CatalogEntry(
        'tonewheel organ percussion second',
        'Tonewheel organ, second-harmonic percussion',
        Family.ORGANS,
        'C2',
        'C7',
        partial(_tonewheel_with_percussion, '808000000', percussion_harmonic=2.0),
    ),
    CatalogEntry(
        'tonewheel organ percussion third',
        'Tonewheel organ, third-harmonic percussion',
        Family.ORGANS,
        'C2',
        'C7',
        partial(_tonewheel_with_percussion, '888000000', percussion_harmonic=3.0),
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
)

# --- Electronic -----------------------------------------------------------------------------


def _synth(  # ruff: ignore[too-many-arguments] - a simple subtractive voice
    wave: str,
    *,
    attack: float,
    release: float,
    low_pass: float | None = None,
    decay: float = 0.0,
    sustain: float = 1.0,
    detune_cents: float = 0.0,
    octave_below: bool = False,
) -> Instrument:
    sources: dict[str, Source] = {'oscillator': Source(wave)}
    if detune_cents > 0.0:
        sources['detuned_up'] = Source(wave, detune_cents=detune_cents, level=0.8)
        sources['detuned_down'] = Source(wave, detune_cents=-detune_cents, level=0.8)
    if octave_below:
        sources['sub'] = Source('square', semitones=-12.0, level=0.5)
    return Instrument(
        sources=sources,
        envelope=envelope(attack=attack, decay=decay, sustain=sustain, release=release),
        filter=None if low_pass is None else Filter(kind='low_pass', cutoff=low_pass),
        normalize=True,
    )


def _theremin() -> Instrument:
    return blown((1.0, 0.08, 0.04), attack=0.12, release=0.25, chorus_cents=4.0)


def _ondes_martenot() -> Instrument:
    return blown((1.0, 0.2, 0.15, 0.05, 0.03), attack=0.06, release=0.2, chorus_cents=3.0)


ELECTRONIC: Final[tuple[CatalogEntry, ...]] = (
    CatalogEntry('theremin', 'Theremin', Family.ELECTRONIC, 'C3', 'C7', _theremin),
    CatalogEntry(
        'ondes martenot', 'Ondes Martenot', Family.ELECTRONIC, 'C1', 'C8', _ondes_martenot
    ),
    CatalogEntry(
        'saw lead',
        'Saw lead',
        Family.ELECTRONIC,
        'C3',
        'C7',
        partial(_synth, 'saw', attack=0.005, release=0.1, low_pass=7000.0),
    ),
    CatalogEntry(
        'square lead',
        'Square lead',
        Family.ELECTRONIC,
        'C3',
        'C7',
        partial(_synth, 'square', attack=0.005, release=0.1, low_pass=6000.0),
    ),
    CatalogEntry(
        'supersaw',
        'Supersaw',
        Family.ELECTRONIC,
        'C2',
        'C7',
        partial(_synth, 'saw', attack=0.01, release=0.3, low_pass=9000.0, detune_cents=12.0),
    ),
    CatalogEntry(
        'synth pad',
        'Synth pad',
        Family.ELECTRONIC,
        'C2',
        'C7',
        partial(_synth, 'saw', attack=0.6, release=1.0, low_pass=2500.0, detune_cents=7.0),
    ),
    CatalogEntry(
        'synth strings',
        'Synth strings',
        Family.ELECTRONIC,
        'C2',
        'C7',
        partial(_synth, 'saw', attack=0.25, release=0.5, low_pass=4500.0, detune_cents=9.0),
    ),
    CatalogEntry(
        'synth brass',
        'Synth brass',
        Family.ELECTRONIC,
        'C2',
        'C6',
        partial(
            _synth,
            'saw',
            attack=0.04,
            decay=0.25,
            sustain=0.75,
            release=0.2,
            low_pass=3500.0,
            detune_cents=5.0,
        ),
    ),
    CatalogEntry(
        'synth bass',
        'Synth bass',
        Family.ELECTRONIC,
        'C1',
        'C4',
        partial(
            _synth,
            'saw',
            attack=0.003,
            decay=0.3,
            sustain=0.5,
            release=0.08,
            low_pass=1200.0,
            octave_below=True,
        ),
    ),
    CatalogEntry(
        'sub bass',
        'Sub bass',
        Family.ELECTRONIC,
        'C1',
        'C3',
        partial(_synth, 'sine', attack=0.005, release=0.1),
    ),
    CatalogEntry(
        'synth pluck',
        'Synth pluck',
        Family.ELECTRONIC,
        'C3',
        'C7',
        partial(_synth, 'saw', attack=0.002, decay=0.3, sustain=0.0, release=0.2, low_pass=3000.0),
    ),
    CatalogEntry(
        'chip square',
        'Chiptune square (50%)',
        Family.ELECTRONIC,
        'A1',
        'C8',
        partial(_synth, 'square', attack=0.0, release=0.02),
    ),
    CatalogEntry(
        'chip pulse 25',
        'Chiptune pulse (25%)',
        Family.ELECTRONIC,
        'A1',
        'C8',
        partial(_synth, 'pulse_25', attack=0.0, release=0.02),
    ),
    CatalogEntry(
        'chip pulse 12',
        'Chiptune pulse (12.5%)',
        Family.ELECTRONIC,
        'A1',
        'C8',
        partial(_synth, 'pulse_12', attack=0.0, release=0.02),
    ),
    CatalogEntry(
        'chip triangle',
        'Chiptune triangle',
        Family.ELECTRONIC,
        'A0',
        'C7',
        partial(_synth, 'triangle', attack=0.0, release=0.02),
    ),
)
