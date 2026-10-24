"""Clockwork Keep's steampunk sound effects as synth recipes.

Brassy squares and saws, filtered noise for steam, low booms. Values are starting points
tuned by ear; edit them freely.
"""

from glitchygames.audio.recipes import SoundRecipe, Tone, Tremolo
from glitchygames.audio.synth import Envelope, Waveform

JUMP = SoundRecipe(
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

LAND = SoundRecipe(
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

COG_PICKUP = SoundRecipe(
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

DEATH = SoundRecipe(
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

GAME_OVER = SoundRecipe(
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

ELEVATOR_CLANK = SoundRecipe(
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
VICTORY = SoundRecipe(
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

ALL_RECIPES = (JUMP, LAND, COG_PICKUP, DEATH, GAME_OVER, ELEVATOR_CLANK, VICTORY)
