"""Instruments, noise, layered sources and ``build_spec``: from the public API to a ``SoundSpec``.

An ``Instrument`` says how something sounds (waves or noise, envelope, filter, drive). Waves may
be given by name; ``build_spec`` resolves them through the current engine context's wave registry,
so a wave registered after the instrument was built still works.
"""

from __future__ import annotations

import math
from dataclasses import KW_ONLY, dataclass
from typing import TYPE_CHECKING, Final, override

from glitchygames.audio.pitch import PitchLike, Tuning, resolve_pitch
from glitchygames.audio.spec import (
    ENVELOPE_PRESETS,
    NOISE_KINDS,
    EnvelopeSpec,
    FilterSpec,
    NoiseSpec,
    NoteEvent,
    PitchCurveSpec,
    PlaybackDefaults,
    SoundSpec,
    SourceSpec,
    check_lfsr_taps,
    default_lfsr_taps,
    default_seed,
    parse_notes,
)
from glitchygames.audio.waves import Wave, current_wave_registry

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from glitchygames.audio import synth

MAXIMUM_SOURCES: Final[int] = 4
DEFAULT_NOTE_LENGTH_SECONDS: Final[float] = 0.25
UNPITCHED_REFERENCE_HZ: Final[float] = 440.0
SEMITONES_PER_OCTAVE: Final[float] = 12.0
DRIVE_HIGHEST: Final[float] = 20.0
LFSR_WIDTHS: Final[tuple[int, ...]] = (15, 7)
PROFILES: Final[tuple[str, ...]] = ('hybrid', 'chip', 'wavetable', 'fm', 'sampler')
DEFAULT_SOURCE_NAME: Final[str] = 'main'


@dataclass(frozen=True, slots=True)
class Filter:
    """A FIR filter for an instrument or a source.

    Attributes:
        kind: ``low_pass`` or ``high_pass``.
        cutoff: The cutoff in hertz.
    """

    kind: str
    cutoff: float

    def to_spec(self) -> FilterSpec:
        """Convert to the spec form (which validates).

        Returns:
            The filter spec.
        """
        return FilterSpec(kind=self.kind, cutoff_hz=self.cutoff)


@dataclass(frozen=True, slots=True)
class PitchCurve:
    """A glide from the source's pitch to ``to``.

    Attributes:
        to: The pitch the glide ends on.
        seconds: How long it takes.
        easing: A name from ``glitchygames.effects.easing``.
    """

    to: PitchLike
    seconds: float
    easing: str = 'linear'


@dataclass(frozen=True, slots=True)
class Noise:
    """A noise layer: white noise or a console-style LFSR.

    Attributes:
        kind: ``white`` or ``lfsr``.
        level: Layer level, 0-1.
        seed: The noise's own seed; None derives it from the sound's seed.
        bits: LFSR width, 15 or 7.
        taps: The two LFSR tap bits; None (the default) is the width's maximal-length set,
            (14, 13) for 15 bits and (6, 5) for 7 bits. Always set after construction.
        rate: LFSR clock rate as a pitch; None follows the note.
    """

    kind: str = 'white'
    _: KW_ONLY
    level: float = 1.0
    seed: int | None = None
    bits: int = 15
    taps: tuple[int, int] | None = None
    rate: PitchLike | None = None

    def __post_init__(self) -> None:
        """Validate the kind, width and level; resolve default taps from the width.

        Raises:
            ValueError: On an unknown kind, an LFSR width other than 15 or 7, an LFSR tap set
                that is not maximal-length, or a level outside 0-1.
        """
        if self.kind not in NOISE_KINDS:
            message = f'unknown noise kind {self.kind!r}; use {" or ".join(NOISE_KINDS)}'
            raise ValueError(message)
        if self.bits not in LFSR_WIDTHS:
            message = f'noise bits must be 15 or 7, got {self.bits}'
            raise ValueError(message)
        taps = self.taps if self.taps is not None else default_lfsr_taps(self.bits)
        object.__setattr__(self, 'taps', taps)  # frozen dataclass: set through object
        if self.kind == 'lfsr':
            check_lfsr_taps(self.bits, taps)
        if not 0.0 <= self.level <= 1.0:
            message = f'noise level must be between 0 and 1, got {self.level}'
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class Source:
    """A layer of an instrument with its own level, tuning and shaping.

    ``Wave.detuned(cents=...)`` makes one. ``content`` is a wave, a wave name (resolved when the
    sound is built) or a ``Noise``.

    Attributes:
        content: The wave, wave name or noise.
        level: Layer level, 0-1.
        semitones: Offset from the note.
        detune_cents: Further offset, in cents.
        pitch: A pitch that overrides the note, or None.
        pitch_curve: A glide, or None.
        envelope: This layer's envelope; None uses the instrument's.
        filter: This layer's filter, or None.
    """

    content: Wave | str | Noise
    _: KW_ONLY
    level: float = 1.0
    semitones: float = 0.0
    detune_cents: float = 0.0
    pitch: PitchLike | None = None
    pitch_curve: PitchCurve | None = None
    envelope: synth.Envelope | EnvelopeSpec | str | None = None
    filter: Filter | None = None

    def __post_init__(self) -> None:
        """Validate the level.

        Raises:
            ValueError: On a level outside 0-1.
        """
        if not 0.0 <= self.level <= 1.0:
            message = f'source level must be between 0 and 1, got {self.level}'
            raise ValueError(message)


def _envelope_spec(envelope: synth.Envelope | EnvelopeSpec | str) -> EnvelopeSpec:
    if isinstance(envelope, str):
        if envelope not in ENVELOPE_PRESETS:
            message = f'unknown envelope {envelope!r}; presets are {", ".join(ENVELOPE_PRESETS)}'
            raise ValueError(message)
        return ENVELOPE_PRESETS[envelope]
    if isinstance(envelope, EnvelopeSpec):
        return envelope
    return EnvelopeSpec.from_legacy(envelope)


def _as_source(entry: Wave | Noise | Source | str) -> Source:
    return entry if isinstance(entry, Source) else Source(entry)


class Instrument:
    """How a sound sounds: immutable, hashable by content.

    Give exactly one of ``wave``, ``noise`` or ``sources`` (one to four layers, in mix order).
    A wave may be a name: it is looked up when the sound is built.
    """

    __slots__ = (
        '_drive',
        '_envelope',
        '_filter',
        '_hard_edges',
        '_live',
        '_normalize',
        '_profile',
        '_seed',
        '_sources',
    )

    def __init__(  # ruff: ignore[too-many-arguments] - mirrors impl spec 8
        self,
        *,
        wave: str | Wave | None = None,
        noise: str | Noise | None = None,
        sources: Mapping[str, Wave | Noise | Source] | None = None,
        envelope: synth.Envelope | EnvelopeSpec | str = 'pluck',
        filter: Filter | None = None,  # ruff: ignore[builtin-argument-shadowing] - impl spec 8
        drive: float = 0.0,
        profile: str = 'hybrid',
        live: bool = False,
        seed: int | None = None,
        normalize: bool = False,
        hard_edges: bool = False,
    ) -> None:
        """Build an instrument.

        Args:
            wave: A wave or a wave name: a single layer.
            noise: A ``Noise`` or a noise kind: a single layer.
            sources: Named layers, one to four, in mix order.
            envelope: A preset name, a ``synth.Envelope`` or an ``EnvelopeSpec``.
            filter: A filter for the whole sound.
            drive: Distortion, 0-20.
            profile: ``hybrid`` (the others are constrained later, M4).
            live: Whether the sound is live (M2).
            seed: The noise seed; None derives it from the sound's name.
            normalize: Normalize the rendered peak.
            hard_edges: Skip the de-click fades.

        Raises:
            ValueError: Unless exactly one of wave, noise and sources is given, on more than
                four sources, on a drive outside 0-20 or an unknown profile or envelope.
        """
        given = [argument for argument in (wave, noise, sources) if argument is not None]
        if len(given) != 1:
            message = 'an instrument takes exactly one of wave, noise or sources'
            raise ValueError(message)
        layers: tuple[tuple[str, Source], ...]
        if sources is not None:
            if not sources:
                message = 'sources cannot be empty'
                raise ValueError(message)
            if len(sources) > MAXIMUM_SOURCES:
                message = f'an instrument has at most {MAXIMUM_SOURCES} sources, got {len(sources)}'
                raise ValueError(message)
            layers = tuple((name, _as_source(entry)) for name, entry in sources.items())
        elif wave is not None:
            layers = ((DEFAULT_SOURCE_NAME, _as_source(wave)),)
        else:
            noise_layer = Noise(noise) if isinstance(noise, str) else noise
            assert noise_layer is not None
            layers = ((DEFAULT_SOURCE_NAME, _as_source(noise_layer)),)
        if not 0.0 <= drive <= DRIVE_HIGHEST:
            message = f'drive must be between 0 and {DRIVE_HIGHEST}, got {drive}'
            raise ValueError(message)
        if profile not in PROFILES:
            message = f'unknown profile {profile!r}; use one of {", ".join(PROFILES)}'
            raise ValueError(message)
        self._sources = layers
        self._envelope = _envelope_spec(envelope)
        self._filter = filter.to_spec() if filter is not None else None
        self._drive = drive
        self._profile = profile
        self._live = live
        self._seed = seed
        self._normalize = normalize
        self._hard_edges = hard_edges

    @property
    def sources(self) -> tuple[tuple[str, Source], ...]:
        """The named layers, in mix order."""
        return self._sources

    @property
    def envelope(self) -> EnvelopeSpec:
        """The instrument's envelope."""
        return self._envelope

    @property
    def filter(self) -> FilterSpec | None:
        """The instrument's filter."""
        return self._filter

    @property
    def drive(self) -> float:
        """Distortion, 0-20."""
        return self._drive

    @property
    def live(self) -> bool:
        """Whether the sound is live."""
        return self._live

    @property
    def seed(self) -> int | None:
        """The given noise seed, or None."""
        return self._seed

    @property
    def normalize(self) -> bool:
        """Whether the rendered peak is normalized."""
        return self._normalize

    @property
    def hard_edges(self) -> bool:
        """Whether the de-click fades are skipped."""
        return self._hard_edges

    @property
    def is_unpitched(self) -> bool:
        """True when every layer is noise."""
        return all(isinstance(source.content, Noise) for _, source in self._sources)

    def _identity(self) -> tuple[object, ...]:
        return (
            self._sources,
            self._envelope,
            self._filter,
            self._drive,
            self._profile,
            self._live,
            self._seed,
            self._normalize,
            self._hard_edges,
        )

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Instrument):
            return NotImplemented
        return self._identity() == other._identity()

    @override
    def __hash__(self) -> int:
        return hash(self._identity())

    @override
    def __repr__(self) -> str:
        return f'Instrument(sources={[name for name, _ in self._sources]!r})'


def _resolved_wave(content: Wave | str) -> Wave:
    if isinstance(content, Wave):
        return content
    try:
        return current_wave_registry()[content]
    except KeyError:
        message = f'unknown wave {content!r}: neither built in nor registered'
        raise ValueError(message) from None


def _hertz(pitch: PitchLike, *, tuning: Tuning, sample_rate: int) -> float:
    return float(resolve_pitch(pitch, tuning=tuning, sample_rate=sample_rate))


def _source_spec(source: Source, *, tuning: Tuning, sample_rate: int) -> SourceSpec:
    content = source.content
    wave: Wave | None = None
    noise_spec: NoiseSpec | None = None
    level = source.level
    duty = 0.5
    if isinstance(content, Noise):
        assert content.taps is not None  # Noise.__post_init__ sets the width's default
        noise_spec = NoiseSpec(
            kind=content.kind,
            bits=content.bits,
            taps=content.taps,
            rate_hz=(
                _hertz(content.rate, tuning=tuning, sample_rate=sample_rate)
                if content.rate is not None
                else None
            ),
            seed=content.seed,
        )
        level *= content.level
    else:
        wave = _resolved_wave(content)
        duty = wave.duty if wave.duty is not None else duty
    pitch_curve = None
    if source.pitch_curve is not None:
        curve = source.pitch_curve
        pitch_curve = PitchCurveSpec(
            target_hz=_hertz(curve.to, tuning=tuning, sample_rate=sample_rate),
            seconds=curve.seconds,
            easing=curve.easing,
        )
    return SourceSpec(
        wave=wave,
        noise=noise_spec,
        level=level,
        semitones=source.semitones,
        detune_cents=source.detune_cents,
        fixed_hz=(
            _hertz(source.pitch, tuning=tuning, sample_rate=sample_rate)
            if source.pitch is not None
            else None
        ),
        pitch_curve=pitch_curve,
        envelope=_envelope_spec(source.envelope) if source.envelope is not None else None,
        filter=source.filter.to_spec() if source.filter is not None else None,
        duty=duty,
    )


def _transposed(hertz: float, *, transpose: float) -> float:
    return hertz * math.pow(2.0, transpose / SEMITONES_PER_OCTAVE)


def _refuse_conflicting_arguments(
    *,
    pitch: PitchLike | None,
    notes: str | Sequence[tuple[PitchLike, float]] | None,
    chord: Sequence[PitchLike] | None,
    length: float | None,
    transpose: float,
) -> None:
    """Refuse identity arguments that cannot go together.

    Raises:
        ValueError: On more than one of pitch, notes and chord, a length that is not above zero
            or is given with notes, or a transpose without notes or chord.
    """
    if sum(argument is not None for argument in (pitch, notes, chord)) > 1:
        message = (
            'pitch, notes and chord are mutually exclusive; use transpose to shift a notes or '
            'chord sound'
        )
        raise ValueError(message)
    if length is not None and not length > 0.0:
        message = f'length must be above zero, got {length}'
        raise ValueError(message)
    if notes is not None and length is not None:
        message = 'length does not apply to notes; give each note its own seconds'
        raise ValueError(message)
    if not math.isclose(transpose, 0.0) and notes is None and chord is None:
        message = 'transpose applies to notes and chord; for a single sound change the pitch'
        raise ValueError(message)


def _note_events(  # ruff: ignore[too-many-arguments] - one call site, mirrors build_spec
    instrument: Instrument,
    *,
    pitch: PitchLike | None,
    notes: str | Sequence[tuple[PitchLike, float]] | None,
    chord: Sequence[PitchLike] | None,
    length: float | None,
    transpose: float,
    tuning: Tuning,
    sample_rate: int,
) -> tuple[tuple[NoteEvent, ...] | None, float]:
    """The note events and the unpitched scale for a build.

    Returns:
        The events (None when no pitch was named) and the unpitched scale.

    Raises:
        ValueError: On the argument conflicts build_spec documents.
    """
    _refuse_conflicting_arguments(
        pitch=pitch, notes=notes, chord=chord, length=length, transpose=transpose
    )
    note_length = length if length is not None else DEFAULT_NOTE_LENGTH_SECONDS
    if notes is not None:
        return (
            tuple(
                NoteEvent(
                    event.start_seconds,
                    _transposed(event.hz, transpose=transpose),
                    event.length_seconds,
                )
                for event in parse_notes(notes, tuning=tuning, sample_rate=sample_rate)
            ),
            1.0,
        )
    if chord is not None:
        if not chord:
            message = 'chord cannot be empty'
            raise ValueError(message)
        return (
            tuple(
                NoteEvent(
                    0.0,
                    _transposed(
                        _hertz(chord_pitch, tuning=tuning, sample_rate=sample_rate),
                        transpose=transpose,
                    ),
                    note_length,
                )
                for chord_pitch in chord
            ),
            1.0,
        )
    if pitch is not None:
        hertz = _hertz(pitch, tuning=tuning, sample_rate=sample_rate)
        scale = hertz / UNPITCHED_REFERENCE_HZ if instrument.is_unpitched else 1.0
        return (NoteEvent(0.0, hertz, note_length),), scale
    if length is not None:
        if not instrument.is_unpitched:
            message = 'length needs a pitch or chord for a pitched instrument'
            raise ValueError(message)
        # An unpitched sound with a length but no pitch: a reference-pitch event carries the length
        return (NoteEvent(0.0, UNPITCHED_REFERENCE_HZ, length),), 1.0
    return None, 1.0


def _refuse_filters_at_or_above_nyquist(instrument: Instrument, *, sample_rate: int) -> None:
    """Refuse a filter cutoff the FIR filter cannot make at this sample rate.

    Raises:
        ValueError: Naming the cutoff and the Nyquist frequency, for the instrument's filter or a
            source's at or above Nyquist.
    """
    nyquist = sample_rate / 2.0
    cutoffs = [
        *([instrument.filter.cutoff_hz] if instrument.filter is not None else []),
        *(source.filter.cutoff for _, source in instrument.sources if source.filter is not None),
    ]
    for cutoff in cutoffs:
        if cutoff >= nyquist:
            message = (
                f'filter cutoff {cutoff} Hz must be below Nyquist ({nyquist} Hz at '
                f'{sample_rate} Hz)'
            )
            raise ValueError(message)


def build_spec(  # ruff: ignore[too-many-arguments] - mirrors the brief's signature
    instrument: Instrument,
    *,
    name: str,
    pitch: PitchLike | None,
    notes: str | Sequence[tuple[PitchLike, float]] | None,
    chord: Sequence[PitchLike] | None,
    length: float | None,
    transpose: float,
    tuning: Tuning,
    sample_rate: int,
    playback_defaults: PlaybackDefaults,
) -> SoundSpec:
    """Turn an instrument and the identity arguments into a ``SoundSpec``.

    Wave names are resolved through the current wave registry here. A single pitch or chord lasts
    ``length`` seconds (default 0.25) before its release. An unpitched instrument given a pitch
    sets ``unpitched_scale`` to ``pitch_hz / 440``. With no pitch, notes or chord the spec's
    ``notes`` is None (the renderer decides), except an unpitched instrument given a ``length``,
    which gets one reference-pitch event carrying it.

    Args:
        instrument: How the sound sounds.
        name: The sound's name (the default seed derives from it).
        pitch: One pitch, or None.
        notes: A melody, or None.
        chord: Pitches played together, or None.
        length: Seconds for a single pitch or chord; None means 0.25.
        transpose: Semitones to shift ``notes`` or ``chord``.
        tuning: The tuning for pitch names.
        sample_rate: The rate to render at.
        playback_defaults: Default playback settings, carried but not part of the identity.

    Returns:
        The spec.
    """
    _refuse_filters_at_or_above_nyquist(instrument, sample_rate=sample_rate)
    events, unpitched_scale = _note_events(
        instrument,
        pitch=pitch,
        notes=notes,
        chord=chord,
        length=length,
        transpose=transpose,
        tuning=tuning,
        sample_rate=sample_rate,
    )
    return SoundSpec(
        name=name,
        sources=tuple(
            _source_spec(source, tuning=tuning, sample_rate=sample_rate)
            for _, source in instrument.sources
        ),
        envelope=instrument.envelope,
        filter=instrument.filter,
        drive=instrument.drive,
        notes=events,
        unpitched_scale=unpitched_scale,
        sample_rate=sample_rate,
        seed=instrument.seed if instrument.seed is not None else default_seed(name),
        normalize=instrument.normalize,
        hard_edges=instrument.hard_edges,
        live=instrument.live,
        tuning_a4=tuning.a4,
        playback_defaults=playback_defaults,
    )
