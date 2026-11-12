"""Electronic instruments: the oscillator voices, chip voices, theremin and ondes Martenot.

The sound is made by electronic circuits alone (Hornbostel-Sachs 53): the family is defined by how
the sound is made, and the owner's decision 3 splits it from the electromechanical instruments
(H-S 51 and 52, in ``keyboards.py``), whose sound starts as a mechanical vibration read
electrically. Most entries are one subtractive shape (``_synth``: a wave, an envelope, an optional
low pass, a detuned pair or a square an octave below); the theremin and ondes Martenot are blown
shapes with a slow attack and a slight chorus. The sound-alikes, listed instruments that share
another entry's build, are in ``electronic_sound_alikes.py``.
"""

from __future__ import annotations

from functools import partial
from typing import Final

from glitchygames.audio.instrument import Filter, Instrument, Source
from glitchygames.audio.instruments.catalog import CatalogEntry, Family, Tag
from glitchygames.audio.instruments.electronic_sound_alikes import ELECTRONIC_SOUND_ALIKES
from glitchygames.audio.instruments.timbres import blown, envelope


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


_ELECTRONIC_BUILDS: Final[tuple[CatalogEntry, ...]] = (
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
        tags=frozenset({Tag.CHIP}),
    ),
    CatalogEntry(
        'chip pulse 25',
        'Chiptune pulse (25%)',
        Family.ELECTRONIC,
        'A1',
        'C8',
        partial(_synth, 'pulse_25', attack=0.0, release=0.02),
        tags=frozenset({Tag.CHIP}),
    ),
    CatalogEntry(
        'chip pulse 12',
        'Chiptune pulse (12.5%)',
        Family.ELECTRONIC,
        'A1',
        'C8',
        partial(_synth, 'pulse_12', attack=0.0, release=0.02),
        tags=frozenset({Tag.CHIP}),
    ),
    CatalogEntry(
        'chip triangle',
        'Chiptune triangle',
        Family.ELECTRONIC,
        'A0',
        'C7',
        partial(_synth, 'triangle', attack=0.0, release=0.02),
        tags=frozenset({Tag.CHIP}),
    ),
)

ELECTRONIC: Final[tuple[CatalogEntry, ...]] = _ELECTRONIC_BUILDS + ELECTRONIC_SOUND_ALIKES
