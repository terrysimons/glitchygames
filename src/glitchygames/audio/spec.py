"""Immutable sound specs: what a compiled sound is, and the key that names it.

A ``SoundSpec`` holds everything that decides what a sound sounds like (sources, envelope, notes,
sample rate, seed, tuning). It is frozen data: the renderer (Task 4) turns it into samples, sound
files (Task 5) produce it, and the library's cache (Task 6) is keyed by ``identity_key``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import sysconfig
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, cast

import numpy as np

from glitchygames.audio.pitch import PitchLike, Tuning, resolve_pitch
from glitchygames.audio.waves import Wave

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.audio import synth

# Bumped whenever the renderer's output changes for the same spec (impl spec 6.2)
AUDIO_RENDER_VERSION: Final[int] = 1
IDENTITY_KEY_HEX_DIGITS: Final[int] = 32  # 128 bits
ENVELOPE_CURVE_PATTERN: Final[re.Pattern[str]] = re.compile(r'^(linear|exponential|steps\(\d+\))$')
FILTER_KINDS: Final[tuple[str, ...]] = ('low_pass', 'high_pass')
REST_TOKEN: Final[str] = '_'  # ruff: ignore[hardcoded-password-string] - a rest, not a password
SEED_BYTE_COUNT: Final[int] = 8


@dataclass(frozen=True, slots=True)
class EnvelopeSpec:
    """An attack/decay/sustain/release envelope, in seconds, with a curve.

    Attributes:
        attack: Seconds from zero to full level.
        decay: Seconds from full level down to ``sustain``.
        sustain: The held level, 0-1.
        release: Seconds from the held level to zero after the note ends.
        curve: ``linear``, ``exponential`` or ``steps(n)``.
    """

    attack: float
    decay: float
    sustain: float
    release: float
    curve: str = 'linear'

    def __post_init__(self) -> None:
        """Validate the stages and the curve.

        Raises:
            ValueError: On a negative time, a sustain outside 0-1 or an unknown curve.
        """
        if min(self.attack, self.decay, self.release) < 0.0:
            message = 'envelope times cannot be negative'
            raise ValueError(message)
        if not 0.0 <= self.sustain <= 1.0:
            message = f'envelope sustain must be between 0 and 1, got {self.sustain}'
            raise ValueError(message)
        if ENVELOPE_CURVE_PATTERN.match(self.curve) is None:
            message = f'unknown envelope curve {self.curve!r}; use linear, exponential or steps(n)'
            raise ValueError(message)

    @classmethod
    def from_legacy(cls, envelope: synth.Envelope) -> EnvelopeSpec:
        """Convert the existing ``synth.Envelope`` (linear stages).

        Args:
            envelope: The legacy envelope.

        Returns:
            The equivalent spec.
        """
        return cls(
            attack=envelope.attack,
            decay=envelope.decay,
            sustain=envelope.sustain_level,
            release=envelope.release,
            curve='linear',
        )


# The presets are this project's own choices for the names in feature spec 5.2
ENVELOPE_PRESETS: Final[dict[str, EnvelopeSpec]] = {
    'pluck': EnvelopeSpec(attack=0.002, decay=0.15, sustain=0.0, release=0.05, curve='exponential'),
    'pad': EnvelopeSpec(attack=0.3, decay=0.2, sustain=0.7, release=0.5, curve='linear'),
    'organ': EnvelopeSpec(attack=0.005, decay=0.0, sustain=1.0, release=0.03, curve='linear'),
    'percussive': EnvelopeSpec(
        attack=0.001, decay=0.2, sustain=0.0, release=0.02, curve='exponential'
    ),
    'swell': EnvelopeSpec(attack=0.4, decay=0.0, sustain=1.0, release=0.3, curve='linear'),
}


@dataclass(frozen=True, slots=True)
class FilterSpec:
    """A FIR filter (the only kind in M1).

    Attributes:
        kind: ``low_pass`` or ``high_pass``.
        cutoff_hz: The cutoff in hertz.
    """

    kind: str
    cutoff_hz: float

    def __post_init__(self) -> None:
        """Validate the kind and cutoff.

        Raises:
            ValueError: On an unknown kind or a cutoff that is not above zero.
        """
        if self.kind not in FILTER_KINDS:
            message = f'unknown filter kind {self.kind!r}; use {" or ".join(FILTER_KINDS)}'
            raise ValueError(message)
        if self.cutoff_hz <= 0.0:
            message = f'filter cutoff must be above zero, got {self.cutoff_hz}'
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class PitchCurveSpec:
    """A glide from the source's pitch to ``target_hz`` over ``seconds``.

    Attributes:
        target_hz: Where the glide ends.
        seconds: How long it takes.
        easing: A name from ``glitchygames.effects.easing``.
    """

    target_hz: float
    seconds: float
    easing: str = 'linear'


@dataclass(frozen=True, slots=True)
class NoiseSpec:
    """A noise source.

    Attributes:
        kind: ``white`` or ``lfsr``.
        bits: LFSR register width (15 or 7).
        taps: The two LFSR tap bits.
        rate_hz: LFSR clock rate; None follows the note's pitch.
        seed: The noise's own seed; None derives it from the sound's seed.
    """

    kind: str
    bits: int
    taps: tuple[int, int]
    rate_hz: float | None
    seed: int | None


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """One layer of a sound: a wave or noise, with its own level, tuning and shaping.

    Attributes:
        wave: The resolved wave, or None for noise.
        noise: The noise settings, or None for a wave.
        level: Layer level, 0-1.
        semitones: Offset from the note, in semitones.
        detune_cents: Further offset, in cents.
        fixed_hz: A pitch that overrides the note, or None.
        pitch_curve: A glide, or None.
        envelope: This layer's envelope, or None for the sound's.
        filter: This layer's filter, or None.
        duty: The pulse duty (0.5 when the wave has none).
    """

    wave: Wave | None
    noise: NoiseSpec | None
    level: float
    semitones: float
    detune_cents: float
    fixed_hz: float | None
    pitch_curve: PitchCurveSpec | None
    envelope: EnvelopeSpec | None
    filter: FilterSpec | None
    duty: float


@dataclass(frozen=True, slots=True)
class NoteEvent:
    """One note of a sound.

    Attributes:
        start_seconds: When it begins.
        hz: Its frequency.
        length_seconds: How long it is held before its release.
    """

    start_seconds: float
    hz: float
    length_seconds: float


@dataclass(frozen=True, slots=True)
class PlaybackDefaults:
    """How a sound plays by default: playback, not what the sound is.

    Attributes:
        bus: The bus name (validated where buses exist, not here).
        volume: Playback volume.
        pan: Playback pan, -1 (left) to 1 (right).
        priority: Voice-stealing priority.
        loop: Whether it loops.
    """

    bus: str = 'effects'
    volume: float = 1.0
    pan: float = 0.0
    priority: int = 50
    loop: bool = False


@dataclass(frozen=True, slots=True)
class SoundSpec:
    """Everything that decides what a compiled sound sounds like.

    ``playback_defaults`` is carried but is not part of ``identity_key``: it says how the sound
    plays, not what it is. ``name`` is part of the key because the default ``seed`` derives from
    it.

    Attributes:
        name: The sound's name.
        sources: One to four layers.
        envelope: The sound's envelope.
        filter: The sound's filter, or None.
        drive: Distortion amount, 0-20.
        notes: The note events, or None when the caller named no pitch.
        unpitched_scale: Scales an unpitched instrument's rates (pitch / 440 Hz), else 1.0.
        sample_rate: The rate to render at.
        seed: The noise seed (derived from the name unless the instrument gave one).
        normalize: Normalize the rendered peak.
        hard_edges: Skip the de-click fades.
        live: Whether this is a live (M2) sound.
        tuning_a4: The A4 frequency the pitches were resolved with.
        playback_defaults: Default playback settings; not part of the identity.
    """

    name: str
    sources: tuple[SourceSpec, ...]
    envelope: EnvelopeSpec
    filter: FilterSpec | None
    drive: float
    notes: tuple[NoteEvent, ...] | None
    unpitched_scale: float
    sample_rate: int
    seed: int
    normalize: bool
    hard_edges: bool
    live: bool
    tuning_a4: float
    playback_defaults: PlaybackDefaults


def default_seed(name: str) -> int:
    """The seed a sound gets when its instrument gives none (impl spec 6.3).

    Args:
        name: The sound's name.

    Returns:
        The first 8 bytes of the SHA-256 of the name, big-endian.
    """
    digest = hashlib.sha256(name.encode()).digest()
    return int.from_bytes(digest[:SEED_BYTE_COUNT], 'big')


def parse_notes(
    notes: str | Sequence[tuple[PitchLike, float]], *, tuning: Tuning, sample_rate: int = 44100
) -> tuple[NoteEvent, ...]:
    """Turn a melody into back-to-back note events.

    Args:
        notes: ``'B5:0.06 _:0.02 E6:0.18'`` (``_`` is a rest) or ``(pitch, seconds)`` pairs,
            where a pitch of ``'_'`` is a rest.
        tuning: The tuning for note names.
        sample_rate: The sample rate, for the Nyquist check.

    Returns:
        One event per non-rest note; each starts where the previous token ended.

    Raises:
        ValueError: On an empty melody, a token without ``:seconds``, or a length not above zero.
    """
    if isinstance(notes, str):
        pairs: list[tuple[PitchLike, float]] = []
        for token in notes.split():
            pitch_text, separator, seconds_text = token.rpartition(':')
            if not separator:
                message = f'note token {token!r} must look like pitch:seconds'
                raise ValueError(message)
            try:
                seconds = float(seconds_text)
            except ValueError:
                message = f'note token {token!r} has no valid length in seconds'
                raise ValueError(message) from None
            pairs.append((pitch_text, seconds))
    else:
        pairs = list(notes)
    if not pairs:
        message = 'notes cannot be empty'
        raise ValueError(message)
    events: list[NoteEvent] = []
    start_seconds = 0.0
    for pitch, seconds in pairs:
        if not seconds > 0.0:
            message = f'note length must be above zero, got {seconds}'
            raise ValueError(message)
        if not (isinstance(pitch, str) and pitch == REST_TOKEN):
            hertz = resolve_pitch(pitch, tuning=tuning, sample_rate=sample_rate)
            events.append(NoteEvent(start_seconds, float(hertz), seconds))
        start_seconds += seconds
    return tuple(events)


def _canonical(value: object) -> Any:  # ruff: ignore[any-type] - JSON-shaped output of any input
    """Reduce a spec value to JSON-able data that is the same in every process.

    Returns:
        Dicts, lists, numbers, strings and None.
    """
    if isinstance(value, Wave):
        # Never id() or hash(): hash randomization would change the key between processes
        return {'wave_sha256': value.identity_digest()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonical(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, tuple | list):
        return [_canonical(item) for item in cast('Sequence[object]', value)]
    if isinstance(value, float):
        return float(value)  # drops float subclasses such as Hz; json writes floats with repr
    return value


def identity_key(spec: SoundSpec) -> str:
    """The cache key of a spec: 128 bits, hex.

    The key is the SHA-256 of canonical JSON (sorted keys; floats written with ``repr``, which
    round-trips exactly) of the spec without its playback defaults, plus ``AUDIO_RENDER_VERSION``,
    the numpy version and the platform tag (impl spec 6.2). Waves enter as a SHA-256 of their
    table bytes, note periods, render path and duty, so the key is stable across processes.

    Args:
        spec: The spec.

    Returns:
        32 hex digits.
    """
    fields = {
        field.name: _canonical(getattr(spec, field.name))
        for field in dataclasses.fields(spec)
        if field.name != 'playback_defaults'
    }
    payload = {
        'spec': fields,
        'render_version': AUDIO_RENDER_VERSION,
        'numpy_version': np.__version__,
        'platform': sysconfig.get_platform(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()[:IDENTITY_KEY_HEX_DIGITS]
