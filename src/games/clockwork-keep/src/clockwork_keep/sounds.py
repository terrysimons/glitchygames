"""Clockwork Keep's steampunk sound effects as synth recipes.

Brassy squares and saws, filtered noise for steam, low booms. Values are starting points
tuned by ear; edit them freely.
"""

import math

from glitchygames.audio.effects import Effect, Tone, Tremolo
from glitchygames.audio.instrument import Filter, Instrument
from glitchygames.audio.live_controls import Parameter, Route
from glitchygames.audio.synth import Envelope, Waveform

JUMP = Effect(
    name='jump',
    volume=0.35,
    tones=(
        Tone(
            waveform=Waveform.SQUARE,
            start_frequency=330.0,
            end_frequency=660.0,
            duration=0.1,
            envelope=Envelope(attack=0.005, decay=0.03, sustain_level=0.6, release=0.05),
            volume=0.6,
        ),
        Tone(
            waveform=Waveform.NOISE,
            start_frequency=0.0,
            duration=0.08,
            envelope=Envelope(attack=0.002, decay=0.02, sustain_level=0.3, release=0.05),
            volume=0.25,
            high_pass_cutoff=2000.0,
        ),
    ),
)

LAND = Effect(
    name='land',
    volume=0.3,
    tones=(
        Tone(
            waveform=Waveform.SINE,
            start_frequency=110.0,
            end_frequency=55.0,
            duration=0.09,
            envelope=Envelope(attack=0.002, decay=0.03, sustain_level=0.5, release=0.05),
            low_pass_cutoff=400.0,
        ),
        Tone(
            waveform=Waveform.NOISE,
            start_frequency=0.0,
            duration=0.04,
            envelope=Envelope(attack=0.001, decay=0.01, sustain_level=0.3, release=0.02),
            volume=0.3,
            low_pass_cutoff=800.0,
        ),
    ),
)

COG_PICKUP = Effect(
    name='cog_pickup',
    volume=0.3,
    tones=(
        Tone(
            waveform=Waveform.TRIANGLE,
            start_frequency=1318.5,
            duration=0.08,
            envelope=Envelope(attack=0.002, decay=0.02, sustain_level=0.5, release=0.05),
        ),
        Tone(
            waveform=Waveform.TRIANGLE,
            start_frequency=1975.5,
            duration=0.12,
            offset=0.07,
            envelope=Envelope(attack=0.002, decay=0.03, sustain_level=0.5, release=0.08),
        ),
    ),
)

DEATH = Effect(
    name='death',
    volume=0.4,
    tones=(
        Tone(
            waveform=Waveform.SAWTOOTH,
            start_frequency=440.0,
            end_frequency=55.0,
            easing='ease_in_quad',
            duration=0.7,
            envelope=Envelope(attack=0.005, decay=0.1, sustain_level=0.8, release=0.3),
            low_pass_cutoff=2500.0,
            tremolo=Tremolo(rate_hz=18.0, depth=0.5),
        ),
    ),
)

GAME_OVER = Effect(
    name='game_over',
    volume=0.4,
    tones=tuple(
        Tone(
            waveform=Waveform.TRIANGLE,
            start_frequency=frequency,
            duration=duration,
            offset=offset,
            envelope=Envelope(attack=0.01, decay=0.05, sustain_level=0.7, release=0.2),
        )
        for frequency, offset, duration in (
            (659.25, 0.0, 0.35),
            (523.25, 0.35, 0.35),
            (440.0, 0.7, 0.6),
        )
    ),
)

ELEVATOR_CLANK = Effect(
    name='elevator_clank',
    volume=0.6,
    tones=(
        Tone(
            waveform=Waveform.NOISE,
            start_frequency=0.0,
            duration=0.25,
            envelope=Envelope(attack=0.001, decay=0.05, sustain_level=0.3, release=0.15),
            volume=0.7,
            distortion=4.0,
            low_pass_cutoff=3000.0,
        ),
        Tone(
            waveform=Waveform.SINE,
            start_frequency=70.0,
            end_frequency=40.0,
            duration=0.9,
            envelope=Envelope(attack=0.002, decay=0.1, sustain_level=0.6, release=0.6),
        ),
        Tone(
            waveform=Waveform.SQUARE,
            start_frequency=880.0,
            duration=0.3,
            offset=0.01,
            envelope=Envelope(attack=0.001, decay=0.02, sustain_level=0.2, release=0.25),
            volume=0.25,
            high_pass_cutoff=600.0,
        ),
    ),
)

# A bell's tone: the fundamental, its octave, and the slightly sharp (inharmonic) overtone near
# 2.76 times the fundamental that makes a struck bell ring rather than hum
BELL_PARTIALS = ((1.0, 1.0), (2.0, 0.35), (2.76, 0.2))


def bell(*, frequency: float, offset: float, duration: float, volume: float) -> tuple[Tone, ...]:
    """Return one struck bell: its partials, each fading out over the bell's duration.

    Args:
        frequency: The fundamental (Hz).
        offset: When it is struck (seconds into the sound).
        duration: How long it rings.
        volume: Its loudness, before the recipe's.

    Returns:
        The bell's tones.

    """
    return tuple(
        Tone(
            waveform=Waveform.SINE,
            start_frequency=frequency * ratio,
            duration=duration,
            offset=offset,
            envelope=Envelope(attack=0.003, decay=0.08, sustain_level=0.5, release=duration * 0.7),
            volume=volume * partial_volume,
        )
        for ratio, partial_volume in BELL_PARTIALS
    )


# Reaching the top of the Clock Face: the clock tower's chime, C5, E5 and G5 climbing, then C6
# ringing out over a deep C3 strike
VICTORY = Effect(
    name='victory',
    volume=0.45,
    tones=(
        *bell(frequency=523.25, offset=0.0, duration=0.45, volume=0.7),
        *bell(frequency=659.25, offset=0.16, duration=0.45, volume=0.7),
        *bell(frequency=783.99, offset=0.32, duration=0.5, volume=0.75),
        *bell(frequency=1046.5, offset=0.5, duration=1.4, volume=0.85),
        *bell(frequency=130.81, offset=0.5, duration=1.6, volume=0.9),
    ),
)

# Every effect the game plays, requested from the sound library when a floor is built
EFFECTS = (JUMP, LAND, COG_PICKUP, DEATH, GAME_OVER, ELEVATOR_CLANK, VICTORY)

# A live sound plays centred, 3 dB down on each side by the constant-power pan law every sound
# pans by; the motor's levels are raised by the same (times the square root of 2), so it sounds
# as loud as it did before live sounds took a pan (the owner, 2026-11-15)
CENTRE_PAN_COMPENSATION = math.sqrt(2.0)

# The elevator motor: a deep, chugging saw whose pitch and level follow the car's speed (the
# ride sets ``speed``, 0 at rest to 1 at the easing's peak slope, every frame). Live: started
# by the ride, which owns it, and cut as the car lands.
ELEVATOR_MOTOR = Instrument(
    wave='saw',
    live=True,
    filter=Filter('low_pass', 600.0),  # keeps the saw deep
    tremolo=Tremolo(rate_hz=8.0, depth=0.4),  # the motor's chug
    parameters={'speed': Parameter(range=(0.0, 1.0), default=0.0)},
    routes=[
        Route(source='speed', destination='pitch', output=(45.0, 110.0)),  # Hz, rest to full
        Route(
            source='speed',
            destination='level',
            output=(0.15 * CENTRE_PAN_COMPENSATION, 0.6 * CENTRE_PAN_COMPENSATION),
        ),
    ],
)
