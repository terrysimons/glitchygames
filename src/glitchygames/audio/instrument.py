"""Instruments, noise, layered sources and ``build_spec``: from the public API to a ``SoundSpec``.

An ``Instrument`` says how something sounds (waves or noise, envelope, filter, drive). Waves may
be given by name; ``build_spec`` resolves them through the current engine context's wave registry,
so a wave registered after the instrument was built still works.
"""

from __future__ import annotations

import math
from dataclasses import KW_ONLY, dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, override

from glitchygames.audio.live_controls import (
    DEFAULT_CHUNK_SECONDS,
    MAXIMUM_CHUNK_SECONDS,
    MAXIMUM_ROUTES,
    MINIMUM_CHUNK_SECONDS,
    SOURCE_LEVEL_DESTINATION,
)
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
    from glitchygames.audio.effects import Tremolo
    from glitchygames.audio.live_controls import Parameter, Route

MAXIMUM_SOURCES: Final[int] = 4
DEFAULT_NOTE_LENGTH_SECONDS: Final[float] = 0.25
UNPITCHED_REFERENCE_HZ: Final[float] = 440.0
SEMITONES_PER_OCTAVE: Final[float] = 12.0
DRIVE_HIGHEST: Final[float] = 20.0
LFSR_WIDTHS: Final[tuple[int, ...]] = (15, 7)
PROFILES: Final[tuple[str, ...]] = ('hybrid', 'chip', 'wavetable', 'fm', 'sampler')
DEFAULT_SOURCE_NAME: Final[str] = 'main'
# Route destinations one route at most may move (no rule combines two); levels multiply
SINGLE_ROUTE: Final[frozenset[str]] = frozenset({
    'pitch',
    'filter.cutoff',
    'tremolo.rate',
    'tremolo.depth',
})
# Route destinations whose output is a fraction, 0-1 (the rest are above 0: Hz)
FRACTION_DESTINATIONS: Final[frozenset[str]] = frozenset({'level', 'tremolo.depth'})


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
        '_chunk_seconds',
        '_drive',
        '_envelope',
        '_filter',
        '_hard_edges',
        '_live',
        '_normalize',
        '_parameters',
        '_profile',
        '_routes',
        '_seed',
        '_sources',
        '_tremolo',
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
        tremolo: Tremolo | None = None,
        parameters: Mapping[str, Parameter] | None = None,
        routes: Sequence[Route] | None = None,
        chunk_seconds: float | None = None,
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
            tremolo: Amplitude modulation for a live sound (rate and depth are route
                destinations: ``tremolo.rate``, ``tremolo.depth``).
            parameters: A live sound's exposed parameters, by name (``audio/live_controls.py``).
            routes: How a live sound's parameters move it, at most ``MAXIMUM_ROUTES``; each
                from one of ``parameters``, a ``sources.<name>.level`` to one of its sources.
            chunk_seconds: A live sound's chunk length, its latency, 0.03-0.5 s; None is 0.1.

        Raises:
            ValueError: Unless exactly one of wave, noise and sources is given, on more than
                four sources, on a drive outside 0-20 or an unknown profile or envelope, and for
                controls (tremolo, parameters, routes) on an instrument that is not live or that
                do not fit it.
        """
        exactly_one_message = 'an instrument takes exactly one of wave, noise or sources'
        if sum(argument is not None for argument in (wave, noise, sources)) > 1:
            raise ValueError(exactly_one_message)
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
        elif noise is not None:
            noise_layer = Noise(noise) if isinstance(noise, str) else noise
            layers = ((DEFAULT_SOURCE_NAME, _as_source(noise_layer)),)
        else:
            # None of the three was given (more than one was refused above)
            raise ValueError(exactly_one_message)
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
        self._tremolo = tremolo
        self._chunk_seconds = chunk_seconds
        self._parameters: tuple[tuple[str, Parameter], ...] = tuple((parameters or {}).items())
        self._routes: tuple[Route, ...] = tuple(routes or ())
        self._check_controls()

    def _check_controls(self) -> None:
        """Refuse controls that need a live instrument or do not fit this one.

        Raises:
            ValueError: Naming what does not fit.
        """
        if not self._live:
            given = [
                name
                for name, value in (
                    ('tremolo', self._tremolo),
                    ('parameters', self._parameters),
                    ('routes', self._routes),
                    ('chunk_seconds', self._chunk_seconds),
                )
                if value
            ]
            if given:
                message = f'{", ".join(given)} only on a live instrument (live=True)'
                raise ValueError(message)
            return
        if self._chunk_seconds is not None and not (
            MINIMUM_CHUNK_SECONDS <= self._chunk_seconds <= MAXIMUM_CHUNK_SECONDS
        ):
            message = (
                f'chunk_seconds must be between {MINIMUM_CHUNK_SECONDS} and '
                f'{MAXIMUM_CHUNK_SECONDS}, got {self._chunk_seconds}'
            )
            raise ValueError(message)
        if len(self._routes) > MAXIMUM_ROUTES:
            message = f'an instrument has at most {MAXIMUM_ROUTES} routes, got {len(self._routes)}'
            raise ValueError(message)
        parameter_names = {name for name, _ in self._parameters}
        source_names = {name for name, _ in self._sources}
        for route in self._routes:
            if route.source not in parameter_names:
                message = f'a route from {route.source!r}: the instrument has no parameter named so'
                raise ValueError(message)
            source_level = SOURCE_LEVEL_DESTINATION.fullmatch(route.destination)
            if source_level is not None and source_level.group('name') not in source_names:
                message = (
                    f'a route to {route.destination}: the instrument has no source named '
                    f"'{source_level.group('name')}'"
                )
                raise ValueError(message)
            self._check_route_fits(route)
        single = [route.destination for route in self._routes if route.destination in SINGLE_ROUTE]
        for destination in set(single):
            if single.count(destination) > 1:
                count = single.count(destination)
                message = f'an instrument takes one route to {destination}, got {count}'
                raise ValueError(message)

    def _check_route_fits(self, route: Route) -> None:
        """Refuse a route to a setting this instrument lacks, or with an output it cannot take.

        Every curve stays between its output's ends (``live_controls`` rule 2), so the ends
        decide: levels and tremolo depth within 0-1; pitch, cutoff and tremolo rate above 0.

        Raises:
            ValueError: Naming the route and what does not fit.
        """
        needs = {
            'filter.cutoff': ('filter', self._filter),
            'tremolo.rate': ('tremolo', self._tremolo),
            'tremolo.depth': ('tremolo', self._tremolo),
        }
        if route.destination in needs and needs[route.destination][1] is None:
            message = f'a route to {route.destination} needs a {needs[route.destination][0]}'
            raise ValueError(message)
        low, high = min(route.output), max(route.output)
        fraction = route.destination in FRACTION_DESTINATIONS or (
            SOURCE_LEVEL_DESTINATION.fullmatch(route.destination) is not None
        )
        fits = (low >= 0.0 and high <= 1.0) if fraction else low > 0.0
        if not fits:
            allowed = 'within 0-1' if fraction else 'above 0'
            message = (
                f'a route to {route.destination} needs an output {allowed}, got {route.output}'
            )
            raise ValueError(message)

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
    def tremolo(self) -> Tremolo | None:
        """A live sound's amplitude modulation, or None."""
        return self._tremolo

    @property
    def chunk_seconds(self) -> float:
        """A live sound's chunk length in seconds, its latency (0.1 unless given)."""
        return DEFAULT_CHUNK_SECONDS if self._chunk_seconds is None else self._chunk_seconds

    @property
    def parameters(self) -> Mapping[str, Parameter]:
        """A live sound's exposed parameters, by name (read-only)."""
        return MappingProxyType(dict(self._parameters))

    @property
    def routes(self) -> tuple[Route, ...]:
        """How a live sound's parameters move it, in order."""
        return self._routes

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
            self._tremolo,
            self._parameters,
            self._routes,
            self.chunk_seconds,
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
        noise_spec = NoiseSpec(
            kind=content.kind,
            bits=content.bits,
            # Noise.__post_init__ already set the width's default taps; this is the same choice,
            # written out because the field's type still allows None
            taps=content.taps if content.taps is not None else default_lfsr_taps(content.bits),
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
