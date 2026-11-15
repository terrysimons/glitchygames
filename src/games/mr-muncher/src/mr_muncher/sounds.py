"""Mr. Muncher's sound effects and jingles (glitchygames/audio/effects.py), and its projector.

All original, and all cinema: eating a sprocket is a popcorn crunch (two slightly different
ones, alternating, so a run of them never repeats exactly), a snack is a clapperboard's clack
and a rising shimmer, a new game counts down like a film leader (a beep a number), and every
take starts with the clapperboard and a bright chord ("ACTION!"). Catching a muncher is a
camera flash, being caught snaps the film and slides down a sad trombone, and THE END is a
falling minor phrase. Values are starting points tuned by ear; edit them freely.
"""

from __future__ import annotations

from glitchygames.audio.effects import Effect, Tone, Tremolo
from glitchygames.audio.instrument import Filter, Instrument
from glitchygames.audio.live_controls import Parameter, Route
from glitchygames.audio.synth import Envelope, Waveform

# One beat of the jingles, in seconds
BEAT_SECONDS = 0.2

# Note frequencies (Hz) the jingles use
NOTE_FREQUENCIES: dict[str, float] = {
    'A2': 110.00,
    'C3': 130.81,
    'G3': 196.00,
    'C4': 261.63,
    'E4': 329.63,
    'F4': 349.23,
    'F#4': 369.99,
    'G4': 392.00,
    'A4': 440.00,
    'C5': 523.25,
    'E5': 659.25,
    'G5': 783.99,
    'C6': 1046.50,
    'E6': 1318.51,
    'G6': 1567.98,
    'C7': 2093.00,
}

# A plucked note: quick attack, short decay to a held level, a little release
NOTE_ENVELOPE = Envelope(attack=0.005, decay=0.05, sustain_level=0.6, release=0.05)
# A click: almost no length at all
CLICK_ENVELOPE = Envelope(attack=0.001, decay=0.01, sustain_level=0.3, release=0.01)


def _melody(
    *, notes: tuple[tuple[str, float], ...], waveform: Waveform, volume: float, start: float = 0.0
) -> tuple[Tone, ...]:
    """Return one tone per note, each starting where the previous one ended.

    Args:
        notes: (note name, length in beats) pairs.
        waveform: The voice.
        volume: Each note's volume.
        start: When the first note starts, in seconds.

    Returns:
        The tones.

    """
    tones: list[Tone] = []
    offset = start
    for name, beats in notes:
        duration = beats * BEAT_SECONDS
        tones.append(
            Tone(
                waveform=waveform,
                start_frequency=NOTE_FREQUENCIES[name],
                duration=duration * 0.95,
                offset=offset,
                envelope=NOTE_ENVELOPE,
                volume=volume,
            )
        )
        offset += duration
    return tuple(tones)


def _clack(*, offset: float = 0.0) -> Tone:
    """Return a clapperboard's clack: a very short, bright burst of noise.

    Args:
        offset: When it sounds, in seconds.

    Returns:
        The tone.

    """
    return Tone(
        waveform=Waveform.NOISE,
        start_frequency=0.0,
        duration=0.03,
        offset=offset,
        envelope=CLICK_ENVELOPE,
        high_pass_cutoff=1500.0,
    )


def _crunch(*, name: str, cutoff: float, pop_frequency: float) -> Effect:
    """Return a popcorn crunch: a short burst of filtered noise over a falling pop.

    Args:
        name: The recipe's name.
        cutoff: The noise's high-pass cutoff (higher is crisper).
        pop_frequency: Where the pop starts falling from.

    Returns:
        The recipe.

    """
    return Effect(
        name=name,
        volume=0.18,
        tones=(
            Tone(
                waveform=Waveform.NOISE,
                start_frequency=0.0,
                duration=0.045,
                envelope=Envelope(attack=0.001, decay=0.015, sustain_level=0.4, release=0.02),
                high_pass_cutoff=cutoff,
                volume=0.8,
            ),
            Tone(
                waveform=Waveform.SINE,
                start_frequency=pop_frequency,
                end_frequency=pop_frequency / 2,
                duration=0.04,
                envelope=Envelope(attack=0.001, decay=0.01, sustain_level=0.5, release=0.02),
                volume=0.6,
            ),
        ),
    )


CRUNCH_ONE = _crunch(name='crunch_one', cutoff=1800.0, pop_frequency=700.0)
CRUNCH_TWO = _crunch(name='crunch_two', cutoff=2600.0, pop_frequency=820.0)
# Played alternately, one per sprocket
CRUNCH_EFFECTS = (CRUNCH_ONE, CRUNCH_TWO)

SUGAR_RUSH = Effect(
    name='sugar_rush',
    volume=0.3,
    tones=(
        _clack(),
        _clack(offset=0.07),
        Tone(
            waveform=Waveform.TRIANGLE,
            start_frequency=600.0,
            end_frequency=1800.0,
            easing='ease_out_quad',
            duration=0.45,
            offset=0.1,
            envelope=Envelope(attack=0.02, decay=0.1, sustain_level=0.6, release=0.2),
            tremolo=Tremolo(rate_hz=30.0, depth=0.4),
        ),
    ),
)

CAMERA_FLASH = Effect(
    name='camera_flash',
    volume=0.32,
    tones=(
        Tone(
            waveform=Waveform.NOISE,
            start_frequency=0.0,
            duration=0.06,
            envelope=Envelope(attack=0.001, decay=0.02, sustain_level=0.4, release=0.03),
            high_pass_cutoff=3000.0,
        ),
        *_melody(
            notes=(('E6', 0.3), ('G6', 0.3), ('C7', 0.8)),
            waveform=Waveform.TRIANGLE,
            volume=0.8,
            start=0.05,
        ),
    ),
)

EAT_BONUS = Effect(
    name='eat_bonus',
    volume=0.3,
    tones=_melody(
        notes=(('C6', 0.5), ('G5', 0.5), ('E6', 0.5), ('G6', 1.0)),
        waveform=Waveform.TRIANGLE,
        volume=1.0,
    ),
)

# Caught: the film snaps, then a sad trombone slides down four notes, sagging on the last
FILM_SNAP = Effect(
    name='film_snap',
    volume=0.4,
    tones=(
        Tone(
            waveform=Waveform.NOISE,
            start_frequency=0.0,
            duration=0.12,
            envelope=Envelope(attack=0.001, decay=0.04, sustain_level=0.3, release=0.06),
            distortion=3.0,
            low_pass_cutoff=4000.0,
        ),
        *(
            Tone(
                waveform=Waveform.SAWTOOTH,
                start_frequency=NOTE_FREQUENCIES[note],
                end_frequency=NOTE_FREQUENCIES[note] * sag,
                duration=duration,
                offset=offset,
                envelope=Envelope(attack=0.02, decay=0.05, sustain_level=0.8, release=0.08),
                low_pass_cutoff=1400.0,
                tremolo=Tremolo(rate_hz=6.0, depth=depth),
                volume=0.7,
            )
            for note, offset, duration, sag, depth in (
                ('G4', 0.2, 0.3, 1.0, 0.1),
                ('F#4', 0.52, 0.3, 1.0, 0.1),
                ('F4', 0.84, 0.3, 1.0, 0.1),
                ('E4', 1.16, 0.9, 0.94, 0.3),
            )
        ),
    ),
)

LEVEL_CLEAR = Effect(
    name='level_clear',
    volume=0.35,
    tones=_melody(
        notes=(('C5', 0.5), ('E5', 0.5), ('G5', 0.5), ('C6', 0.5), ('G5', 0.5), ('C6', 1.5)),
        waveform=Waveform.SQUARE,
        volume=0.6,
    )
    + _melody(
        notes=(('C3', 1.0), ('G3', 1.0), ('C4', 2.0)),
        waveform=Waveform.TRIANGLE,
        volume=1.0,
    ),
)

EXTRA_LIFE = Effect(
    name='extra_life',
    volume=0.3,
    tones=_melody(
        notes=(('E6', 0.5), ('G6', 0.5), ('E6', 0.5), ('G6', 0.5), ('E6', 0.5), ('G6', 1.0)),
        waveform=Waveform.TRIANGLE,
        volume=1.0,
    ),
)

# A film leader's countdown beep, one per number
COUNTDOWN_BEEP = Effect(
    name='countdown_beep',
    volume=0.25,
    tones=(
        Tone(
            waveform=Waveform.SINE,
            start_frequency=1000.0,
            duration=0.12,
            envelope=Envelope(attack=0.003, decay=0.02, sustain_level=0.8, release=0.03),
        ),
    ),
)

# ACTION!: the clapperboard, then a bright major chord over a low root
ACTION = Effect(
    name='action',
    volume=0.32,
    tones=(
        _clack(),
        *(
            Tone(
                waveform=waveform,
                start_frequency=NOTE_FREQUENCIES[note],
                duration=0.5,
                offset=0.05,
                envelope=Envelope(attack=0.005, decay=0.1, sustain_level=0.5, release=0.25),
                volume=volume,
            )
            for note, waveform, volume in (
                ('C5', Waveform.SQUARE, 0.35),
                ('E5', Waveform.SQUARE, 0.35),
                ('G5', Waveform.SQUARE, 0.35),
                ('C4', Waveform.TRIANGLE, 1.0),
            )
        ),
    ),
)

THE_END = Effect(
    name='the_end',
    volume=0.35,
    tones=_melody(
        notes=(('E5', 1.0), ('C5', 1.0), ('A4', 2.0)),
        waveform=Waveform.TRIANGLE,
        volume=0.8,
    )
    + _melody(notes=(('A2', 4.0),), waveform=Waveform.TRIANGLE, volume=1.0),
)

# The projector behind play: filtered noise that flutters like a film projector's shutter. The
# game sets its ``cutoff`` and ``flutter`` (Hz) for the moment; each routes one to one. No
# smoothing: a cutoff change is crossfaded across a chunk, and the flutter's phase carries on,
# as the older live voice did.
PROJECTOR_CUTOFF_RANGE_HZ = (300.0, 2000.0)  # frightened, slowest, to eyes going home
PROJECTOR_FLUTTER_RANGE_HZ = (8.0, 40.0)
PROJECTOR = Instrument(
    noise='white',
    live=True,
    filter=Filter('low_pass', 500.0),
    tremolo=Tremolo(rate_hz=20.0, depth=0.8),
    parameters={
        'cutoff': Parameter(range=PROJECTOR_CUTOFF_RANGE_HZ, default=500.0, smoothing_ms=0.0),
        'flutter': Parameter(range=PROJECTOR_FLUTTER_RANGE_HZ, default=20.0, smoothing_ms=0.0),
    },
    routes=[
        Route(source='cutoff', destination='filter.cutoff', output=PROJECTOR_CUTOFF_RANGE_HZ),
        Route(source='flutter', destination='tremolo.rate', output=PROJECTOR_FLUTTER_RANGE_HZ),
    ],
)

# Every effect the game plays, requested from the sound library when a level is built
EFFECTS = (
    CRUNCH_ONE,
    CRUNCH_TWO,
    SUGAR_RUSH,
    CAMERA_FLASH,
    EAT_BONUS,
    FILM_SNAP,
    LEVEL_CLEAR,
    EXTRA_LIFE,
    COUNTDOWN_BEEP,
    ACTION,
    THE_END,
)
