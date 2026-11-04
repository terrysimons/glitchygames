"""The building blocks the instrument catalog is made of: overtone series and instrument shapes.

Every catalog instrument is an ordinary ``Instrument`` (waves, noise, up to four sources, an
envelope, filters and drive), built by one of the shapes here:

- ``blown``: a sustained tone (flutes, reeds, brass, bowed strings, voices, organs): a wave from
  an overtone series, optional detuned copies (a chorus or a section), breath or bow noise, an
  optional bright ``bite`` layer that fades after the attack (a brass or reed onset).
- ``plucked``: a string that is plucked or struck once and rings down (guitars, lutes, harps,
  pianos): the series shaped by where the string is plucked, optional extra courses (a
  mandolin's pairs, a twelve-string's octaves) and a pick or hammer noise.
- ``struck``: a bar, bell, plate or membrane whose partials are not harmonics (mallets, bells,
  steel pans, timpani): up to four sine partials at their own frequency ratios, each with its
  own decay, so the high partials die first, as they do in a struck bar.
- ``drum``: an unpitched hit: a tone that may glide (a kick's drop) and filtered noise, each
  decaying on its own.

The overtone shapes: ``falling_series`` (each harmonic quieter by a slope in dB per octave; with
``odd_only`` the closed-pipe spectrum of a clarinet), ``plucked_series`` (a string plucked at a
fraction of its length has no harmonics with a node there: the comb of sin(pi n p), standard
string acoustics) and ``formant_series`` (harmonics weighted by resonance peaks: a voice's
vowel, an instrument's body).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instrument import Filter, Instrument, Noise, PitchCurve, Source
from glitchygames.audio.pitch import Hz
from glitchygames.audio.spec import EnvelopeSpec
from glitchygames.audio.waves import Harmonics, Wave

if TYPE_CHECKING:
    from collections.abc import Sequence

# Harmonics' fields from harmonic 1 upward (sub_octave and fifth, the organ's 16' and 5 1/3'
# bars, lie below or between harmonics and are set only through drawbars)
HARMONIC_FIELD_NAMES: Final[tuple[str, ...]] = (
    'fundamental',
    'octave',
    'octave_and_fifth',
    'two_octaves',
    *(f'harmonic_{number}' for number in range(5, 33)),
)
HIGHEST_HARMONIC: Final[int] = len(HARMONIC_FIELD_NAMES)
DECIBELS_PER_FACTOR_OF_TEN: Final[float] = 20.0
QUIETEST_LEVEL: Final[float] = 1e-4  # quieter harmonics are left out (-80 dB)
CHORUS_LEVEL: Final[float] = 0.7
BITE_DECAY_SECONDS: Final[float] = 0.09
BITE_SUSTAIN: Final[float] = 0.15
MAXIMUM_COURSES: Final[int] = 2  # the string, two courses and the pick: the four sources


def decibels_to_level(decibels: float) -> float:
    """A level from decibels (0 dB is 1.0).

    Args:
        decibels: The level in decibels.

    Returns:
        The linear level.
    """
    return 10.0 ** (decibels / DECIBELS_PER_FACTOR_OF_TEN)


def harmonics_from_levels(levels: Sequence[float]) -> Harmonics:
    """Harmonics from a list of levels, harmonic 1 first.

    Args:
        levels: One level per harmonic from the fundamental up, at most 32.

    Returns:
        The harmonics (levels below -80 dB are left at zero).

    Raises:
        ValueError: With more than 32 levels or none.
    """
    if not levels or len(levels) > HIGHEST_HARMONIC:
        message = f'give between 1 and {HIGHEST_HARMONIC} harmonic levels, got {len(levels)}'
        raise ValueError(message)
    values = {
        name: (level if level >= QUIETEST_LEVEL else 0.0)
        for name, level in zip(HARMONIC_FIELD_NAMES, levels, strict=False)
    }
    return Harmonics(**values)


def falling_series(
    *,
    count: int,
    decibels_per_octave: float,
    odd_only: bool = False,
    even_level: float = 1.0,
) -> tuple[float, ...]:
    """Harmonic levels falling by a slope: harmonic n at -slope x log2(n) dB.

    A sawtooth falls 6 dB per octave (1/n); a bright brass or double reed falls less, a flute
    much more.

    Args:
        count: How many harmonics, from the fundamental.
        decibels_per_octave: The slope.
        odd_only: Leave out the even harmonics (a closed pipe: the clarinet, the crumhorn).
        even_level: Scale the even harmonics by this (a clarinet keeps a trace of them).

    Returns:
        The levels, harmonic 1 first.
    """
    levels: list[float] = []
    for harmonic in range(1, count + 1):
        level = decibels_to_level(-decibels_per_octave * math.log2(harmonic))
        if harmonic % 2 == 0:
            level *= 0.0 if odd_only else even_level
        levels.append(level)
    return tuple(levels)


def plucked_series(
    *, count: int, decibels_per_octave: float, pluck_position: float
) -> tuple[float, ...]:
    """A string's harmonics when plucked or struck at ``pluck_position`` of its length.

    Harmonic n is scaled by |sin(pi n p)|: a harmonic with a node where the string is plucked
    is not excited (plucked at a fifth of the length, the fifth, tenth... harmonics are gone).
    The levels are scaled so the loudest is 1.

    Args:
        count: How many harmonics.
        decibels_per_octave: The underlying slope.
        pluck_position: Where the string is plucked, as a fraction of its length (0-0.5).

    Returns:
        The levels, harmonic 1 first.
    """
    slope = falling_series(count=count, decibels_per_octave=decibels_per_octave)
    shaped = [
        level * abs(math.sin(math.pi * harmonic * pluck_position))
        for harmonic, level in enumerate(slope, start=1)
    ]
    loudest = max(shaped)
    return tuple(level / loudest for level in shaped)


@dataclass(frozen=True, slots=True)
class Formant:
    """A resonance peak: its centre in hertz, its bandwidth in hertz and its gain in decibels."""

    hertz: float
    bandwidth: float
    decibels: float


def formant_series(
    *,
    fundamental_hz: float,
    formants: Sequence[Formant],
    source_decibels_per_octave: float = 6.0,
    floor_decibels: float = -40.0,
) -> tuple[float, ...]:
    """Harmonic levels of a tone at ``fundamental_hz`` heard through resonance peaks.

    The source-filter model of a voice (Fant, *Acoustic Theory of Speech Production*): a source
    whose harmonics fall by ``source_decibels_per_octave`` (the glottal pulses fall about 12 dB
    an octave and the lips' radiation lifts them 6, so 6 net), times the resonances' response
    at each harmonic. Each resonance responds as a damped resonator does,
    1 / sqrt(1 + (2 (f - centre) / bandwidth)^2) scaled by its gain, so its skirts reach far
    enough that the fundamental is never lost (a gaussian peak left a soprano's "ee" with almost
    no fundamental: a thin tone whose waveform repeats at a higher octave). The table's
    harmonics keep their levels at every pitch, so the peaks sit where they belong only near
    ``fundamental_hz`` (pick the middle of the instrument's range) and move with the note
    elsewhere.

    Args:
        fundamental_hz: The pitch the peaks are placed for.
        formants: The resonance peaks.
        source_decibels_per_octave: The source's slope.
        floor_decibels: The response between peaks.

    Returns:
        The levels (as many harmonics as fit below 12 kHz, at most 32), the loudest 1.
    """
    count = max(1, min(HIGHEST_HARMONIC, int(12000.0 // fundamental_hz)))
    source = falling_series(count=count, decibels_per_octave=source_decibels_per_octave)
    levels: list[float] = []
    for harmonic, source_level in enumerate(source, start=1):
        frequency = harmonic * fundamental_hz
        response = decibels_to_level(floor_decibels)
        for formant in formants:
            distance = 2.0 * (frequency - formant.hertz) / formant.bandwidth
            response += decibels_to_level(formant.decibels) / math.sqrt(1.0 + distance**2)
        levels.append(source_level * response)
    loudest = max(levels)
    return tuple(level / loudest for level in levels)


def wave_from_levels(levels: Sequence[float]) -> Wave:
    """A wave made of harmonics at ``levels``.

    Args:
        levels: One level per harmonic, the fundamental first.

    Returns:
        The wave.
    """
    return Wave.from_harmonics(harmonics_from_levels(levels))


def envelope(
    *,
    attack: float,
    decay: float = 0.0,
    sustain: float = 1.0,
    release: float,
    curve: str = 'exponential',
) -> EnvelopeSpec:
    """An envelope (a shorthand with a sustained default).

    Args:
        attack: Seconds to full level.
        decay: Seconds down to the sustain level.
        sustain: The held level, 0-1.
        release: Seconds to silence after the note ends.
        curve: ``linear``, ``exponential`` or ``steps(n)``.

    Returns:
        The envelope.
    """
    return EnvelopeSpec(attack=attack, decay=decay, sustain=sustain, release=release, curve=curve)


def noise_layer(
    *,
    level: float,
    low_pass: float | None = None,
    high_pass: float | None = None,
    layer_envelope: EnvelopeSpec | None = None,
    seed: int | None = None,
) -> Source:
    """White noise with at most one filter (low-pass wins: one filter per source).

    Args:
        level: The layer's level, 0-1.
        low_pass: A low-pass cutoff in hertz, or None.
        high_pass: A high-pass cutoff in hertz, or None.
        layer_envelope: The layer's own envelope, or None for the instrument's.
        seed: The noise seed, or None (derived from the sound's name).

    Returns:
        The noise source.
    """
    layer_filter = None
    if low_pass is not None:
        layer_filter = Filter(kind='low_pass', cutoff=low_pass)
    elif high_pass is not None:
        layer_filter = Filter(kind='high_pass', cutoff=high_pass)
    return Source(
        Noise('white', level=level, seed=seed), filter=layer_filter, envelope=layer_envelope
    )


def _instrument_filter(*, low_pass: float | None, high_pass: float | None) -> Filter | None:
    if low_pass is not None:
        return Filter(kind='low_pass', cutoff=low_pass)
    if high_pass is not None:
        return Filter(kind='high_pass', cutoff=high_pass)
    return None


def blown(  # ruff: ignore[too-many-arguments] - each keyword is one physical trait
    levels: Sequence[float],
    *,
    attack: float,
    release: float,
    decay: float = 0.0,
    sustain: float = 1.0,
    breath: float = 0.0,
    breath_low_pass: float = 4000.0,
    low_pass: float | None = None,
    high_pass: float | None = None,
    drive: float = 0.0,
    chorus_cents: float = 0.0,
    bite_levels: Sequence[float] | None = None,
) -> Instrument:
    """A sustained tone: a wind, a bowed string, an organ pipe or a voice.

    Args:
        levels: The tone's harmonic levels.
        attack: Seconds to full level (a flute speaks slower than a trumpet).
        release: Seconds to silence after the note.
        decay: Seconds from the attack peak down to ``sustain``.
        sustain: The held level.
        breath: Breath or bow noise level (0 for none).
        breath_low_pass: The breath noise's low-pass cutoff.
        low_pass: A low-pass cutoff for the whole instrument (a darker bell or body), or None.
        high_pass: A high-pass cutoff when there is no low-pass (a mute), or None.
        drive: Distortion, 0-20 (a hard-blown reed's grit).
        chorus_cents: When above 0, a second copy of the tone this many cents sharp (two
            players, or a slightly unsteady pitch beating against itself).
        bite_levels: A brighter series that fades after the attack, or None.

    Returns:
        The instrument.
    """
    tone_wave = wave_from_levels(levels)
    sources: dict[str, Source] = {'tone': Source(tone_wave)}
    if chorus_cents > 0.0:
        sources['chorus'] = Source(tone_wave, detune_cents=chorus_cents, level=CHORUS_LEVEL)
    if bite_levels is not None:
        sources['bite'] = Source(
            wave_from_levels(bite_levels),
            level=0.6,
            envelope=envelope(
                attack=attack, decay=BITE_DECAY_SECONDS, sustain=BITE_SUSTAIN, release=release
            ),
        )
    if breath > 0.0:
        sources['breath'] = noise_layer(level=breath, low_pass=breath_low_pass)
    return Instrument(
        sources=sources,
        envelope=envelope(attack=attack, decay=decay, sustain=sustain, release=release),
        filter=_instrument_filter(low_pass=low_pass, high_pass=high_pass),
        drive=drive,
        normalize=True,
    )


def drawbar_organ(setting: str, *, attack: float = 0.005, release: float = 0.06) -> Instrument:
    """An organ registration from drawbar digits (``Harmonics.drawbars``).

    Args:
        setting: Nine digits 0-8 for the 16', 5 1/3', 8', 4', 2 2/3', 2', 1 3/5', 1 1/3' and
            1' bars.
        attack: Seconds to full level.
        release: Seconds to silence.

    Returns:
        The instrument.
    """
    return Instrument(
        wave=Wave.from_harmonics(Harmonics.drawbars(setting)),
        envelope=envelope(attack=attack, release=release, curve='linear'),
        normalize=True,
    )


@dataclass(frozen=True, slots=True)
class Course:
    """An extra string sounding with each note: its offset in semitones and cents, its level."""

    semitones: float = 0.0
    cents: float = 0.0
    level: float = 0.8


def plucked(  # ruff: ignore[too-many-arguments] - each keyword is one physical trait
    levels: Sequence[float],
    *,
    ring_seconds: float,
    release: float = 0.25,
    attack: float = 0.002,
    sustain: float = 0.0,
    courses: Sequence[Course] = (),
    pick: float = 0.0,
    pick_high_pass: float = 2000.0,
    low_pass: float | None = None,
    high_pass: float | None = None,
    drive: float = 0.0,
) -> Instrument:
    """A string plucked or struck once: it rings down over ``ring_seconds``.

    Args:
        levels: The string's harmonic levels (``plucked_series``).
        ring_seconds: Seconds from the pluck down to ``sustain``.
        release: Seconds to silence once the note is let go (a damped string).
        attack: Seconds to full level.
        sustain: The level it rings down to (above 0 for an amplified, driven guitar).
        courses: Up to two more strings per note (paired courses, octave strings).
        pick: The pick, nail or hammer noise level (0 for none).
        pick_high_pass: The pick noise's high-pass cutoff.
        low_pass: A low-pass cutoff for the instrument, or None.
        high_pass: A high-pass cutoff when there is no low-pass, or None.
        drive: Distortion, 0-20.

    Returns:
        The instrument.

    Raises:
        ValueError: With more than two courses.
    """
    if len(courses) > MAXIMUM_COURSES:
        message = f'a plucked instrument takes at most two extra courses, got {len(courses)}'
        raise ValueError(message)
    string_wave = wave_from_levels(levels)
    sources: dict[str, Source] = {'string': Source(string_wave)}
    for number, course in enumerate(courses, start=1):
        sources[f'course_{number}'] = Source(
            string_wave, semitones=course.semitones, detune_cents=course.cents, level=course.level
        )
    if pick > 0.0:
        sources['pick'] = noise_layer(
            level=pick,
            high_pass=pick_high_pass,
            layer_envelope=envelope(attack=0.0005, decay=0.02, sustain=0.0, release=0.01),
        )
    return Instrument(
        sources=sources,
        envelope=envelope(attack=attack, decay=ring_seconds, sustain=sustain, release=release),
        filter=_instrument_filter(low_pass=low_pass, high_pass=high_pass),
        drive=drive,
        normalize=True,
    )


@dataclass(frozen=True, slots=True)
class Partial:
    """One partial of a struck bar or bell.

    Attributes:
        ratio: Its frequency as a multiple of the note's (need not be a whole number).
        level: Its level, 0-1.
        ring_seconds: Seconds it takes to die away.
        wave: The wave it is drawn with (a sine for a pure partial).
    """

    ratio: float
    level: float
    ring_seconds: float
    wave: str = 'sine'

    @property
    def semitones(self) -> float:
        """The ratio as an offset in semitones."""
        return 12.0 * math.log2(self.ratio)


def struck(
    partials: Sequence[Partial],
    *,
    release: float,
    mallet: float = 0.0,
    mallet_low_pass: float = 3000.0,
    low_pass: float | None = None,
) -> Instrument:
    """A bar, bell, plate or tuned membrane: partials at their own ratios, each dying away.

    Args:
        partials: One to four partials (three with a mallet noise).
        release: Seconds to silence after the note is let go (keep it near the longest ring, so
            a short note still rings: a struck bar is not damped by letting go).
        mallet: The mallet's noise level (0 for none).
        mallet_low_pass: The mallet noise's low-pass cutoff (soft mallets are darker).
        low_pass: A low-pass cutoff for the instrument, or None.

    Returns:
        The instrument.

    Raises:
        ValueError: With no partials, or more than the four sources allow.
    """
    room = 3 if mallet > 0.0 else 4
    if not partials or len(partials) > room:
        message = f'a struck instrument takes 1 to {room} partials here, got {len(partials)}'
        raise ValueError(message)
    sources: dict[str, Source] = {}
    for number, partial in enumerate(partials, start=1):
        sources[f'partial_{number}'] = Source(
            partial.wave,
            semitones=partial.semitones,
            level=partial.level,
            envelope=envelope(
                attack=0.001, decay=partial.ring_seconds, sustain=0.0, release=release
            ),
        )
    if mallet > 0.0:
        sources['mallet'] = noise_layer(
            level=mallet,
            low_pass=mallet_low_pass,
            layer_envelope=envelope(attack=0.0005, decay=0.015, sustain=0.0, release=0.01),
        )
    return Instrument(
        sources=sources,
        envelope=envelope(attack=0.0, release=release),
        filter=_instrument_filter(low_pass=low_pass, high_pass=None),
        normalize=True,
    )


@dataclass(frozen=True, slots=True)
class Tone:
    """A drum's pitched part: a fixed pitch that may glide, and how long it rings.

    Attributes:
        hertz: Where it starts.
        ring_seconds: Seconds it takes to die away.
        glide_to: Where it glides to, or None.
        glide_seconds: How long the glide takes.
        level: Its level, 0-1.
        wave: The wave it is drawn with.
    """

    hertz: float
    ring_seconds: float
    glide_to: float | None = None
    glide_seconds: float = 0.05
    level: float = 1.0
    wave: str = 'sine'


def drum(  # ruff: ignore[too-many-arguments] - each keyword is one physical trait
    *,
    tones: Sequence[Tone] = (),
    noise: float = 0.0,
    noise_ring_seconds: float = 0.1,
    noise_low_pass: float | None = None,
    noise_high_pass: float | None = None,
    tail: float = 0.3,
    attack: float = 0.0,
    drive: float = 0.0,
) -> Instrument:
    """An unpitched hit: fixed tones (they ignore the note's pitch) and filtered noise.

    Args:
        tones: Up to three (four without noise) pitched parts.
        noise: The noise level (0 for none).
        noise_ring_seconds: Seconds the noise takes to die away.
        noise_low_pass: The noise's low-pass cutoff, or None.
        noise_high_pass: The noise's high-pass cutoff when there is no low-pass, or None.
        tail: Seconds the sound may ring after the note ends.
        attack: Seconds to full level (a brush swish, a gong's bloom).
        drive: Distortion, 0-20.

    Returns:
        The instrument.

    Raises:
        ValueError: With nothing to sound, or more parts than the four sources allow.
    """
    room = 3 if noise > 0.0 else 4
    if len(tones) > room or (not tones and noise <= 0.0):
        message = f'a drum takes noise or 1 to {room} tones here, got {len(tones)} tones'
        raise ValueError(message)
    sources: dict[str, Source] = {}
    for number, tone in enumerate(tones, start=1):
        glide = (
            PitchCurve(to=Hz(tone.glide_to), seconds=tone.glide_seconds, easing='ease_out_quad')
            if tone.glide_to is not None
            else None
        )
        sources[f'tone_{number}'] = Source(
            tone.wave,
            pitch=Hz(tone.hertz),
            pitch_curve=glide,
            level=tone.level,
            envelope=envelope(attack=attack, decay=tone.ring_seconds, sustain=0.0, release=tail),
        )
    if noise > 0.0:
        sources['noise'] = noise_layer(
            level=noise,
            low_pass=noise_low_pass,
            high_pass=noise_high_pass,
            layer_envelope=envelope(
                attack=attack, decay=noise_ring_seconds, sustain=0.0, release=tail
            ),
        )
    return Instrument(
        sources=sources,
        envelope=envelope(attack=0.0, release=tail),
        drive=drive,
        normalize=True,
    )


def with_drones(
    chanter: Instrument, *, drones: Sequence[tuple[float, float]], drone_wave: Wave
) -> Instrument:
    """A chanter with fixed-pitch drones sounding under every note (a bagpipe).

    Args:
        chanter: The chanter: its ``tone`` source and, if any, its ``breath`` are kept.
        drones: (hertz, level) for each drone, at most two with breath, three without.
        drone_wave: The drones' wave.

    Returns:
        The instrument.

    Raises:
        ValueError: With more drones than the four sources allow.
    """
    kept = {name: source for name, source in chanter.sources if name in {'tone', 'breath'}}
    if len(drones) > 4 - len(kept):
        message = f'room for {4 - len(kept)} drones, got {len(drones)}'
        raise ValueError(message)
    sources = dict(kept)
    for number, (hertz, level) in enumerate(drones, start=1):
        sources[f'drone_{number}'] = Source(drone_wave, pitch=Hz(hertz), level=level)
    assert chanter.envelope is not None
    return Instrument(
        sources=sources,
        envelope=chanter.envelope,
        filter=None
        if chanter.filter is None
        else Filter(kind=chanter.filter.kind, cutoff=chanter.filter.cutoff_hz),
        drive=chanter.drive,
        normalize=True,
    )
