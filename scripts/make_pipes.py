"""Two pipe instruments built on the M1 sound API, rendered to WAV files for listening.

Run from the repository root: ``uv run python scripts/make_pipes.py [OUTPUT_DIRECTORY]``.

Great Highland bagpipe vs uilleann pipes: both are reed chanters over drones, but they differ in
pitch centre, brightness, loudness, drone weight and articulation:

- Highland: chanter "A" near 480 Hz (pipers tune sharp of concert A), very bright and nasal (strong
  upper harmonics, a little reed grit), loud; two tenor drones an octave below the chanter's low A
  (beating slightly against each other) and a bass drone two octaves below. The chanter never
  stops, so repeated notes are separated by short high-G grace notes rather than silence.
- Uilleann: concert D (D4 = 293.66 Hz), sweeter and softer (upper harmonics fall away quickly,
  gently low-passed), drones in D an octave apart and much quieter, and the chanter can be closed
  on the knee, so notes can be detached with real silence (staccato).

Scale values for the Highland chanter are the commonly published modern pipe-chanter frequencies
(low A ~480 Hz with a just-intonation-like scale); treat them as a starting point to tune by ear.
"""

from __future__ import annotations

import operator
import string
import sys
import wave
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from glitchygames.audio import Harmonics, Hz, Instrument, Noise, Tuning, Wave
from glitchygames.audio.instrument import Filter, Source, build_spec
from glitchygames.audio.render import render_sound
from glitchygames.audio.spec import EnvelopeSpec, PlaybackDefaults

if TYPE_CHECKING:
    from collections.abc import Sequence

    import numpy.typing as npt

    from glitchygames.audio.pitch import PitchLike

SAMPLE_RATE = 44100
# Where the WAV files go without an argument (git-ignored)
DEFAULT_OUTPUT_DIRECTORY = Path('build') / 'pipes'

# --- Great Highland bagpipe --------------------------------------------------------------------

HIGHLAND_SCALE = {
    'LG': 422.0,
    'LA': 480.0,
    'B': 537.0,
    'C': 600.0,
    'D': 640.0,
    'E': 720.0,
    'F': 800.0,
    'HG': 864.0,
    'HA': 960.0,
}
HIGHLAND_TENOR_DRONE_HZ = HIGHLAND_SCALE['LA'] / 2.0  # an octave below low A
HIGHLAND_BASS_DRONE_HZ = HIGHLAND_SCALE['LA'] / 4.0  # two octaves below low A
HIGHLAND_GRACE_SECONDS = 0.03  # a high-G grace note between melody notes

# A bright, nasal reed: upper harmonics stay strong instead of falling away
HIGHLAND_CHANTER_HARMONICS = Harmonics(
    fundamental=1.0,
    octave=0.95,
    octave_and_fifth=0.85,
    two_octaves=0.8,
    harmonic_5=0.75,
    harmonic_6=0.65,
    harmonic_7=0.55,
    harmonic_8=0.5,
    harmonic_9=0.42,
    harmonic_10=0.36,
    harmonic_11=0.3,
    harmonic_12=0.25,
)
# Drones: buzzy, but darker than the chanter
HIGHLAND_DRONE_HARMONICS = Harmonics(
    fundamental=1.0,
    octave=0.7,
    octave_and_fifth=0.55,
    two_octaves=0.4,
    harmonic_5=0.3,
    harmonic_6=0.22,
    harmonic_7=0.15,
    harmonic_8=0.1,
)
HIGHLAND_LEGATO = EnvelopeSpec(attack=0.006, decay=0.0, sustain=1.0, release=0.02, curve='linear')

highland_chanter = Instrument(
    sources={
        'reed': Source(
            Wave.from_harmonics(HIGHLAND_CHANTER_HARMONICS),
            level=1.0,
            filter=Filter(kind='low_pass', cutoff=6500.0),
        ),
        # Reed buzz: a little noise, kept below the hiss region so the drive cannot make it harsh
        'buzz': Source(
            Noise('white', level=0.012, seed=11), filter=Filter(kind='low_pass', cutoff=4500.0)
        ),
    },
    envelope=HIGHLAND_LEGATO,
    drive=1.25,  # a little grit: the chanter's reed is hard-driven
    filter=Filter(kind='high_pass', cutoff=300.0),
    seed=1,
    normalize=True,  # peak to -1 dBFS before conversion, so nothing clips
)
highland_drones = Instrument(
    sources={
        'tenor_one': Source(
            Wave.from_harmonics(HIGHLAND_DRONE_HARMONICS),
            pitch=Hz(HIGHLAND_TENOR_DRONE_HZ),
            level=0.55,
        ),
        'tenor_two': Source(
            Wave.from_harmonics(HIGHLAND_DRONE_HARMONICS),
            pitch=Hz(HIGHLAND_TENOR_DRONE_HZ),
            detune_cents=3.0,
            level=0.55,
        ),
        'bass': Source(
            Wave.from_harmonics(HIGHLAND_DRONE_HARMONICS),
            pitch=Hz(HIGHLAND_BASS_DRONE_HZ),
            level=0.7,
        ),
    },
    envelope=EnvelopeSpec(attack=0.25, decay=0.0, sustain=1.0, release=0.4, curve='exponential'),
    seed=2,
    normalize=True,  # peak to -1 dBFS before conversion, so nothing clips
)


def highland_melody(
    names_and_beats: list[tuple[str, float]], *, beat_seconds: float
) -> list[tuple[float, float]]:
    """Melody notes with a high-G grace note before each one that repeats the previous note.

    Args:
        names_and_beats: (scale name, length in beats) pairs.
        beat_seconds: How long one beat lasts.

    Returns:
        (frequency, seconds) pairs, graces included.
    """
    events: list[tuple[float, float]] = []
    previous = None
    for name, beats in names_and_beats:
        seconds = beats * beat_seconds
        if name == previous:
            events.append((HIGHLAND_SCALE['HG'], HIGHLAND_GRACE_SECONDS))
            seconds -= HIGHLAND_GRACE_SECONDS
        events.append((HIGHLAND_SCALE[name], seconds))
        previous = name
    return events


# An original phrase in the pipe scale (A mixolydian), with repeated notes to show the graces
HIGHLAND_PHRASE = [
    ('LA', 1),
    ('LA', 1),
    ('B', 0.5),
    ('C', 0.5),
    ('D', 1),
    ('E', 1.5),
    ('F', 0.5),
    ('E', 1),
    ('C', 1),
    ('LA', 1),
    ('B', 1),
    ('C', 2),
    ('E', 1),
    ('E', 1),
    ('HG', 0.5),
    ('F', 0.5),
    ('E', 1),
    ('C', 1),
    ('B', 1),
    ('LA', 2),
    ('LA', 2),
]

# --- Uilleann pipes ----------------------------------------------------------------------------

UILLEANN_SCALE = {
    'D': 293.66,
    'E': 329.63,
    'F#': 369.99,
    'G': 392.00,
    'A': 440.00,
    'B': 493.88,
    'C#': 554.37,
    'D2': 587.33,
    'E2': 659.26,
}
# A sweeter reed: upper harmonics fall away quickly
UILLEANN_CHANTER_HARMONICS = Harmonics(
    fundamental=1.0,
    octave=0.55,
    octave_and_fifth=0.4,
    two_octaves=0.26,
    harmonic_5=0.17,
    harmonic_6=0.1,
    harmonic_7=0.06,
    harmonic_8=0.035,
)
# Drones: smooth, nearly pure, an octave apart in D
UILLEANN_DRONE_HARMONICS = Harmonics(
    fundamental=1.0, octave=0.3, octave_and_fifth=0.12, two_octaves=0.05
)

uilleann_chanter = Instrument(
    sources={
        'reed': Source(Wave.from_harmonics(UILLEANN_CHANTER_HARMONICS), level=1.0),
        'breath': Source(
            Noise('white', level=0.015, seed=21), filter=Filter(kind='low_pass', cutoff=3000.0)
        ),
    },
    envelope=EnvelopeSpec(
        attack=0.012, decay=0.04, sustain=0.85, release=0.03, curve='exponential'
    ),
    filter=Filter(kind='low_pass', cutoff=3500.0),
    seed=3,
    normalize=True,  # peak to -1 dBFS before conversion, so nothing clips
)
uilleann_drones = Instrument(
    sources={
        'tenor': Source(
            Wave.from_harmonics(UILLEANN_DRONE_HARMONICS), pitch=Hz(146.83), level=0.35
        ),
        'baritone': Source(
            Wave.from_harmonics(UILLEANN_DRONE_HARMONICS), pitch=Hz(73.42), level=0.4
        ),
        'bass': Source(Wave.from_harmonics(UILLEANN_DRONE_HARMONICS), pitch=Hz(36.71), level=0.45),
    },
    envelope=EnvelopeSpec(attack=0.4, decay=0.0, sustain=1.0, release=0.5, curve='exponential'),
    filter=Filter(kind='low_pass', cutoff=2000.0),
    seed=4,
    normalize=True,  # peak to -1 dBFS before conversion, so nothing clips
)


def uilleann_melody(
    names_and_beats: list[tuple[str, float, bool]], *, beat_seconds: float
) -> list[tuple[float | str, float]]:
    """Melody notes; a detached (staccato) note closes the chanter for its last fifth.

    Args:
        names_and_beats: (scale name, length in beats, detached) triples.
        beat_seconds: How long one beat lasts.

    Returns:
        (frequency or ``'_'`` for silence, seconds) pairs.
    """
    events: list[tuple[float | str, float]] = []
    for name, beats, detached in names_and_beats:
        seconds = beats * beat_seconds
        if detached:
            events.extend([(UILLEANN_SCALE[name], seconds * 0.8), ('_', seconds * 0.2)])
        else:
            events.append((UILLEANN_SCALE[name], seconds))
    return events


# An original jig-like phrase in D, mixing detached and legato notes
UILLEANN_PHRASE = [
    ('D', 1, True),
    ('F#', 0.5, True),
    ('A', 0.5, True),
    ('D2', 1, False),
    ('B', 0.5, False),
    ('A', 0.5, True),
    ('F#', 1, True),
    ('A', 0.5, True),
    ('B', 0.5, True),
    ('A', 1, False),
    ('F#', 0.5, False),
    ('E', 0.5, True),
    ('D', 1, True),
    ('E', 0.5, True),
    ('F#', 0.5, True),
    ('G', 1, False),
    ('B', 0.5, False),
    ('A', 0.5, True),
    ('F#', 1, False),
    ('E', 1, False),
    ('D', 2, False),
]

# Regulators: keyed pipes the piper presses with the wrist to play short chords under the tune.
# Reedy like the chanter but a little darker, voiced below it; stabs land on the off-beats.
UILLEANN_REGULATOR_HARMONICS = Harmonics(
    fundamental=1.0,
    octave=0.6,
    octave_and_fifth=0.5,
    two_octaves=0.35,
    harmonic_5=0.25,
    harmonic_6=0.15,
)
UILLEANN_REGULATOR_CHORDS = {
    'D': (146.83, 185.00, 220.00),  # D3 F#3 A3
    'G': (196.00, 246.94, 293.66),  # G3 B3 D4
    'A': (220.00, 277.18, 329.63),  # A3 C#4 E4
}
UILLEANN_REGULATOR_STAB_SECONDS = 0.14
uilleann_regulators = Instrument(
    wave=Wave.from_harmonics(UILLEANN_REGULATOR_HARMONICS),
    envelope=EnvelopeSpec(attack=0.008, decay=0.06, sustain=0.6, release=0.04, curve='exponential'),
    filter=Filter(kind='low_pass', cutoff=3000.0),
    seed=5,
    normalize=True,  # peak to -1 dBFS before conversion, so nothing clips
)
# One chord per half bar of the four-beat bars of UILLEANN_PHRASE; a stab on each off-beat,
# and the last chord held under the final note
UILLEANN_REGULATOR_HALF_BARS = ['D', 'D', 'D', 'A', 'G', 'A', 'A', 'D']

# --- Sí Bheag, Sí Mhór -------------------------------------------------------------------------
#
# A slow air usually credited to Turlough O'Carolan (1670-1738), probably his first composition
# (Wikipedia, https://en.wikipedia.org/wiki/S%C3%AD_Bheag,_S%C3%AD_Mh%C3%B3r); public domain.
# Melody notes from the traditional D major, 3/4, AABB setting given in The Fiddler's Companion
# (Andrew Kuntz, https://www.ibiblio.org/fiddlers/SIA_SIO.htm), which cites Bunting (1796) among
# its sources. Only the melody is taken from there; the pipe arrangement (drones, regulator
# chords, articulation) is this script's own. Durations are in eighth notes (six to a bar).

SI_BHEAG_SCALE = {
    'D4': 293.66,
    'E4': 329.63,
    'F#4': 369.99,
    'A4': 440.00,
    'B4': 493.88,
    'C#5': 554.37,
    'D5': 587.33,
    'E5': 659.26,
    'F#5': 739.99,
    'G5': 783.99,
    'A5': 880.00,
    'B5': 987.77,
}
SI_BHEAG_PICKUP = [('D5', 1), ('E5', 1)]
SI_BHEAG_PART_A = [
    [('F#5', 3), ('E5', 1), ('D5', 2)],
    [('D5', 3), ('E5', 1), ('D5', 2)],
    [('B4', 4), ('A4', 2)],
    [('F#4', 4), ('A4', 2)],
    [('B4', 1), ('A4', 1), ('B4', 1), ('C#5', 1), ('D5', 2)],
    [('E5', 4), ('D5', 1), ('E5', 1)],
    [('F#5', 4), ('E5', 2)],
    [('D5', 4), ('F#5', 2)],
    [('B4', 4), ('E5', 2)],
    [('A4', 4), ('D5', 2)],
    [('F#4', 4), ('E4', 2)],
    [('D4', 4), ('F#5', 2)],
    [('B4', 4), ('E5', 2)],
    [('A4', 4), ('D5', 1), ('C#5', 1)],
    [('D5-', 6)],
    [('D5', 4)],  # the long D tied over two bars ('-' ties into the next note)
]
SI_BHEAG_PART_B = [
    [('F#5', 3), ('E5', 1), ('D5', 2)],
    [('E5', 1), ('D5', 1), ('E5', 1), ('F#5', 1), ('A5', 2)],
    [('B5', 4), ('A5', 2)],
    [('F#5', 4), ('E5', 1), ('D5', 1)],
    [('E5', 4), ('A5', 2)],
    [('F#5', 4), ('E5', 2)],
    [('D5', 4), ('B4', 2)],
    [('B4', 4), ('B4', 1), ('A4', 1)],
    [('F#4', 4), ('E4', 2)],
    [('D4', 4), ('F#5', 2)],
    [('B4', 4), ('E5', 2)],
    [('A4', 4), ('A5', 2)],
    [('B5', 1), ('A5', 1), ('G5', 1), ('F#5', 1), ('E5', 1), ('D5', 1)],
    [('E5', 4), ('D5', 1), ('C#5', 1)],
    [('D5-', 6)],
    [('D5', 4)],
]
SI_BHEAG_EIGHTH_SECONDS = (
    0.32 / 2
)  # 2x the leisurely 0.32 s (the owner's tempo): about 188 quarter notes a minute
SI_BHEAG_CUT_SECONDS = 0.025  # a cut: a flick of a higher note before a long note
SI_BHEAG_LONG_NOTE_EIGHTHS = 3  # a note this long (or longer) opening a bar gets a cut
SI_BHEAG_CUT_EXEMPT_NOTES = {'A5', 'B5'}  # already at or above the cut's own note
SI_BHEAG_CHORD_FOR_NOTE = {  # the regulator chord that fits each bar's longest note
    'D': 'D',
    'F#': 'D',
    'A': 'D',
    'B': 'G',
    'G': 'G',
    'E': 'A',
    'C#': 'A',
}


def _pitch_class(note_name: str) -> str:
    return note_name.rstrip('-').rstrip(string.digits)


def si_bheag_bars() -> list[list[tuple[str, int]]]:
    """The whole AABB form as bars; each part's pickup notes join the end of the bar before.

    Returns:
        The bars, each a list of (written note name, eighths) pairs.
    """
    bars: list[list[tuple[str, int]]] = []
    for part in (SI_BHEAG_PART_A, SI_BHEAG_PART_A, SI_BHEAG_PART_B, SI_BHEAG_PART_B):
        if bars:
            bars[-1] += SI_BHEAG_PICKUP
        bars.extend([list(bar) for bar in part])
    bars[-1] += [('_', 2)]  # end on the held D: two eighths of silence close the last bar
    return bars


def si_bheag_melody(bars: list[list[tuple[str, int]]]) -> list[tuple[float | str, float]]:
    """Legato chanter events for the tune.

    The pickup comes first, then a cut before each long note that starts a bar, a brief closing
    of the chanter between repeated notes, and tied notes held as one.

    Args:
        bars: The bars from ``si_bheag_bars``.

    Returns:
        (frequency or ``'_'`` for silence, seconds) pairs.
    """
    events: list[tuple[float | str, float]] = []
    previous = None
    tied = False
    for bar in [list(SI_BHEAG_PICKUP), *bars]:
        for index, (written_name, eighths) in enumerate(bar):
            name = written_name.rstrip('-')
            seconds = eighths * SI_BHEAG_EIGHTH_SECONDS
            if name == '_':
                events.append(('_', seconds))
                previous, tied = None, False
                continue
            if tied:
                # the tied continuation: lengthen the held note instead of striking it again
                pitch, held = events[-1]
                events[-1] = (pitch, held + seconds)
                tied = written_name.endswith('-')
                continue
            if (
                index == 0
                and eighths >= SI_BHEAG_LONG_NOTE_EIGHTHS
                and name not in SI_BHEAG_CUT_EXEMPT_NOTES
            ):
                # a cut: a flick of high A (or B above it) just before the long note
                events.append((SI_BHEAG_SCALE['A5'], SI_BHEAG_CUT_SECONDS))
                seconds -= SI_BHEAG_CUT_SECONDS
            if name == previous:
                # the same note again: close the chanter for a moment so the repeat is heard
                events.append(('_', 0.04))
                seconds -= 0.04
            events.append((SI_BHEAG_SCALE[name], seconds))
            previous = name
            tied = written_name.endswith('-')
    return events


def si_bheag_regulator_layers(
    bars: list[list[tuple[str, int]]], *, start_frame: int
) -> list[tuple[npt.NDArray[np.float64], int, float]]:
    """Soft regulator chords on beats two and three of each bar.

    The tune's own beat one is the melody.

    Args:
        bars: The bars from ``si_bheag_bars``.
        start_frame: The frame where the first bar begins.

    Returns:
        (samples, start frame, gain) mix layers.
    """
    stabs = {
        name: render(
            uilleann_regulators,
            name=f'si_bheag_regulator_{name}',
            chord=[Hz(frequency) for frequency in frequencies],
            length=UILLEANN_REGULATOR_STAB_SECONDS * 1.6,
        )
        for name, frequencies in UILLEANN_REGULATOR_CHORDS.items()
    }
    layers: list[tuple[npt.NDArray[np.float64], int, float]] = []
    bar_start_eighths = 0
    for bar in bars:
        sounding = [note for note in bar if note[0] != '_']
        if sounding:  # a bar of rests gets no chords, but its time still passes
            longest = max(sounding, key=operator.itemgetter(1))
            chord = SI_BHEAG_CHORD_FOR_NOTE[_pitch_class(longest[0])]
            for beat in (1, 2):  # beats two and three, counted from zero
                seconds = (bar_start_eighths + beat * 2) * SI_BHEAG_EIGHTH_SECONDS
                layers.append((stabs[chord], start_frame + round(seconds * SAMPLE_RATE), 0.3))
        bar_start_eighths += sum(eighths for _, eighths in bar)
    return layers


# --- Rendering ---------------------------------------------------------------------------------


def render(  # ruff: ignore[too-many-arguments] - mirrors build_spec's identity arguments
    instrument: Instrument,
    *,
    name: str,
    notes: Sequence[tuple[PitchLike, float]] | None = None,
    pitch: PitchLike | None = None,
    chord: Sequence[PitchLike] | None = None,
    length: float | None = None,
) -> npt.NDArray[np.float64]:
    """Render an instrument to float samples at ``SAMPLE_RATE``.

    Args:
        instrument: The instrument to play.
        name: The sound's name (part of its identity).
        notes: (pitch, seconds) pairs for a melody.
        pitch: A single pitch, held for ``length``.
        chord: Several pitches sounded together for ``length``.
        length: How long a single pitch or chord lasts, in seconds.

    Returns:
        The mono samples.
    """
    spec = build_spec(
        instrument,
        name=name,
        pitch=pitch,
        notes=notes,
        chord=chord,
        length=length,
        transpose=0.0,
        tuning=Tuning(),
        sample_rate=SAMPLE_RATE,
        playback_defaults=PlaybackDefaults(),
    )
    return render_sound(spec).samples


def regulator_layers(
    *, start_frame: int, beat_seconds: float
) -> list[tuple[npt.NDArray[np.float64], int, float]]:
    """The regulator stabs as mix layers: two off-beat stabs per half bar, the last chord held.

    Args:
        start_frame: The frame where the chanter enters.
        beat_seconds: How long one beat lasts.

    Returns:
        (samples, start frame, gain) mix layers.
    """
    stabs = {
        name: render(
            uilleann_regulators,
            name=f'regulator_{name}',
            chord=[Hz(frequency) for frequency in frequencies],
            length=UILLEANN_REGULATOR_STAB_SECONDS,
        )
        for name, frequencies in UILLEANN_REGULATOR_CHORDS.items()
    }
    layers: list[tuple[npt.NDArray[np.float64], int, float]] = []
    for half_bar, chord_name in enumerate(UILLEANN_REGULATOR_HALF_BARS):
        half_bar_start = half_bar * 2 * beat_seconds
        last = half_bar == len(UILLEANN_REGULATOR_HALF_BARS) - 1
        for off_beat in (0.5,) if last else (0.5, 1.5):
            offset = start_frame + round((half_bar_start + off_beat * beat_seconds) * SAMPLE_RATE)
            layers.append((stabs[chord_name], offset, 0.45))
        if last:
            held = render(
                uilleann_regulators,
                name='regulator_final',
                chord=[Hz(f) for f in UILLEANN_REGULATOR_CHORDS[chord_name]],
                length=2 * beat_seconds,
            )
            layers.append((
                held,
                start_frame + round((half_bar_start + beat_seconds) * SAMPLE_RATE),
                0.4,
            ))
    return layers


def mix(*layers: tuple[npt.NDArray[np.float64], int, float]) -> npt.NDArray[np.float64]:
    """Sum (samples, start frame, gain) layers into one buffer, normalized to -1 dBFS.

    Args:
        layers: The (samples, start frame, gain) layers to sum.

    Returns:
        The mixed samples.
    """
    total = max(start + len(samples) for samples, start, _ in layers)
    output = np.zeros(total)
    for samples, start, gain in layers:
        output[start : start + len(samples)] += samples * gain
    return output * (10 ** (-1 / 20) / np.max(np.abs(output)))


def write_wav(path: Path, samples: npt.NDArray[np.float64]) -> None:
    """Write mono float samples as a 16-bit PCM WAV file at ``SAMPLE_RATE``.

    Args:
        path: The file to write.
        samples: The mono samples, nominally within -1.0 to 1.0.
    """
    pcm = np.clip(np.round(samples * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        file.writeframes(pcm.tobytes())


def main() -> None:
    """Render the Highland and uilleann pipe demos into the first argument's directory.

    Without an argument they go to ``DEFAULT_OUTPUT_DIRECTORY``.
    """
    output_directory = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT_DIRECTORY
    output_directory.mkdir(parents=True, exist_ok=True)

    # Highland: drones strike in, chanter enters after a second, all keep sounding to the end
    chanter = render(
        highland_chanter,
        name='highland_chanter',
        notes=highland_melody(HIGHLAND_PHRASE, beat_seconds=0.32),
    )
    drone_seconds = 1.0 + len(chanter) / SAMPLE_RATE + 0.5
    drones = render(
        highland_drones,
        name='highland_drones',
        pitch=Hz(HIGHLAND_TENOR_DRONE_HZ),
        length=drone_seconds,
    )
    highland = mix((drones, 0, 0.55), (chanter, SAMPLE_RATE, 1.0))
    write_wav(output_directory / 'highland_bagpipe.wav', highland)

    # Uilleann: drones softly under a lighter chanter with detached notes, regulator chords beneath
    beat_seconds = 0.28
    chanter_start = int(0.8 * SAMPLE_RATE)
    chanter = render(
        uilleann_chanter,
        name='uilleann_chanter',
        notes=uilleann_melody(UILLEANN_PHRASE, beat_seconds=beat_seconds),
    )
    drone_seconds = 0.8 + len(chanter) / SAMPLE_RATE + 0.6
    drones = render(uilleann_drones, name='uilleann_drones', pitch=Hz(146.83), length=drone_seconds)
    uilleann = mix(
        (drones, 0, 0.35),
        (chanter, chanter_start, 0.8),
        *regulator_layers(start_frame=chanter_start, beat_seconds=beat_seconds),
    )
    write_wav(
        output_directory / 'uilleann_pipes_without_regulators.wav',
        mix((drones, 0, 0.35), (chanter, chanter_start, 0.8)) * (10 ** (-8 / 20)),
    )
    # Quieter overall than the Highland pipe: scale to about -9 dBFS peak
    write_wav(output_directory / 'uilleann_pipes.wav', uilleann * (10 ** (-8 / 20)))

    # Sí Bheag, Sí Mhór on the uilleann pipes: drones, chanter, regulators
    bars = si_bheag_bars()
    chanter = render(uilleann_chanter, name='si_bheag_chanter', notes=si_bheag_melody(bars))
    chanter_start = SAMPLE_RATE  # drones sound for a second first
    first_bar_start = chanter_start + round(
        len(SI_BHEAG_PICKUP) * SI_BHEAG_EIGHTH_SECONDS * SAMPLE_RATE
    )
    drones = render(
        uilleann_drones,
        name='si_bheag_drones',
        pitch=Hz(146.83),
        length=1.0 + len(chanter) / SAMPLE_RATE + 1.0,
    )
    tune = mix(
        (drones, 0, 0.35),
        (chanter, chanter_start, 0.8),
        *si_bheag_regulator_layers(bars, start_frame=first_bar_start),
    )
    write_wav(output_directory / 'si_bheag_si_mhor.wav', tune * (10 ** (-8 / 20)))

    # Chanter-only single notes for side-by-side comparison of the two reeds on the same pitch class
    for label, instrument, frequency in (
        ('highland_chanter_A', highland_chanter, 480.0),
        ('uilleann_chanter_A', uilleann_chanter, 440.0),
    ):
        note = render(instrument, name=label, pitch=Hz(frequency), length=1.5)
        write_wav(
            output_directory / f'{label}.wav', note * (10 ** (-1 / 20) / np.max(np.abs(note)))
        )
    sys.stdout.write(f'wrote {sorted(path.name for path in output_directory.glob("*.wav"))}\n')


if __name__ == '__main__':
    main()
