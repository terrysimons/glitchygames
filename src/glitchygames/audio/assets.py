"""Sound files: the v1 TOML schema, v0 recipes and the short-name index.

A sound file is TOML with a ``[glitchygames]`` header (``kind = "sounds"``, ``version = 1``) and
any number of ``[waves.*]``, ``[instruments.*]`` and ``[sounds.*]`` tables (impl spec 6.1). A
file without a header whose tables are ``[recipes.<name>]`` is a version 0 recipe file. Games refer
to a sound by short name (``'coin'``) or by path (``'sounds/pickups.toml#coin'``, feature spec 3.2).

``load_sound_file`` reads and validates one file; it builds the file's waves and instruments but
registers and compiles nothing (compiling and caching are the library's job).
``ShortNameIndex`` finds which file defines a short name.

Every table is a pydantic v2 model with ``extra='forbid'``. A pydantic ``loc`` tuple is rendered
as a TOML path (``instruments.pickup.sources.tone.wave``); an unknown field gets a "did you mean"
from ``difflib.get_close_matches``, and a field that belongs to a later milestone is refused with
"<field> arrives in <milestone>" (AUD-ASSET-003).
"""

import dataclasses
import difflib
import logging
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Final, Self, cast

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from glitchygames.audio.exceptions import SoundAssetError, SoundRecipeError
from glitchygames.audio.instrument import (
    DRIVE_HIGHEST,
    MAXIMUM_SOURCES,
    PROFILES,
    Filter,
    Instrument,
    Noise,
    PitchCurve,
    Source,
)
from glitchygames.audio.pitch import PitchLike, Tuning, resolve_pitch
from glitchygames.audio.recipes import SoundRecipe, Tone
from glitchygames.audio.spec import (
    ENVELOPE_CURVE_PATTERN,
    ENVELOPE_PRESETS,
    FILTER_KINDS,
    NOISE_KINDS,
    REST_TOKEN,
    EnvelopeSpec,
    PlaybackDefaults,
    check_lfsr_taps,
    parse_notes,
)
from glitchygames.audio.waves import (
    BUILT_IN_WAVE_NAMES,
    CYCLE,
    LEVEL,
    POINT_SHAPES,
    Harmonics,
    Wave,
    WavePoint,
    WaveRegistry,
    current_wave_registry,
)
from glitchygames.effects.easing import get_easing
from glitchygames.engine_context import EngineContext

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

log: logging.Logger = logging.getLogger('game.audio.assets')

CURRENT_SCHEMA_VERSION: Final[int] = 1
LEGACY_SCHEMA_VERSION: Final[int] = 0
# The fields a version 0 recipe and tone are read from (the keys SoundRecipe.to_dict writes)
LEGACY_RECIPE_FIELDS: Final[frozenset[str]] = frozenset({'volume', 'peak', 'tones'})
LEGACY_TONE_FIELDS: Final[frozenset[str]] = frozenset(
    field_info.name for field_info in dataclasses.fields(Tone)
)
SOUND_FILE_KIND: Final[str] = 'sounds'
SOUND_FILE_SUFFIX: Final[str] = '.toml'
RECORDED_SOUND_SUFFIXES: Final[tuple[str, ...]] = ('.wav', '.ogg')
PATH_REFERENCE_SUFFIXES: Final[tuple[str, ...]] = (SOUND_FILE_SUFFIX, *RECORDED_SOUND_SUFFIXES)
INSTRUMENT_SEPARATOR: Final[str] = '#'
# The default buses; custom buses are added in code, so a file can name only these
DEFAULT_BUS_NAMES: Final[tuple[str, ...]] = ('music', 'effects', 'ui', 'ambience', 'dialogue')
MAXIMUM_CHORD_PITCHES: Final[int] = 8
MAXIMUM_NOTES: Final[int] = 256
NOTE_PAIR_LENGTH: Final[int] = 2
SEMITONES_PER_OCTAVE: Final[float] = 12.0
PITCH_VALIDATION_SAMPLE_RATE: Final[int] = 44100
UNKNOWN_FIELDS_ERROR: Final = 'unknown_fields'
UNKNOWN_FIELDS_MESSAGE: Final = 'unknown fields'
FOLLOW_THE_NOTE: Final[str] = 'pitch'  # an LFSR rate that follows the note

# Fields the schema names (impl spec 6.1) whose milestone has not landed: a file that uses one is
# refused with "<field> arrives in <milestone>" instead of a plain unknown-field error. A field
# that a table does accept now (``bits`` of an LFSR, ``loop`` of a sound) never reaches this table.
FIELDS_ARRIVING_LATER: Final[Mapping[str, str]] = MappingProxyType({
    'live': 'M2',
    'bits': 'M2',
    'sample_rate_reduction': 'M2',
    'parameters': 'M2',
    'routes': 'M2',
    'vibrato': 'M4',
    'lfos': 'M4',
    'glide': 'M4',
    'bend_range': 'M4',
    'algorithm': 'M4',
    'operators': 'M4',
    'feedback': 'M4',
    'delay': 'M4',
    'wow_flutter': 'M4',
    'reverb': 'M5',
    'samples': 'M4',
    'resolution_bits': 'M4',
    'sprite': 'M4',
    'wavetable': 'M4',
    'sample': 'M4',
    'position': 'M4',
    'root': 'M4',
    'loop': 'M4',
})
# A filter's own later fields (its ``envelope`` is not the instrument's, which exists now)
FILTER_FIELDS_ARRIVING_LATER: Final[Mapping[str, str]] = MappingProxyType({
    'resonance': 'M2',
    'envelope': 'M2',
})
# Values of a field that belong to a later milestone
FILTER_KINDS_ARRIVING_LATER: Final[Mapping[str, str]] = MappingProxyType({'band_pass': 'M2'})
NOISE_KINDS_ARRIVING_LATER: Final[Mapping[str, str]] = MappingProxyType({'pink': 'M2'})

type PitchValue = str | float
type NoteList = str | tuple[tuple[PitchValue, float], ...]


def _suggestion(word: str, candidates: Sequence[str]) -> str:
    """Return ``; did you mean 'x'?`` for the closest candidate, or an empty string."""
    close = difflib.get_close_matches(word, candidates, n=1)
    return f"; did you mean '{close[0]}'?" if close else ''


class _Table(BaseModel):
    """A TOML table: unknown fields are refused with a suggestion or a milestone."""

    model_config = ConfigDict(extra='forbid', frozen=True, populate_by_name=True)

    arriving_later: ClassVar[Mapping[str, str]] = FIELDS_ARRIVING_LATER
    unknown_noun: ClassVar[str] = 'field'

    @model_validator(mode='before')
    @classmethod
    def _refuse_unknown_fields(cls, data: object) -> object:
        """Refuse every key the table does not define, naming each with its reason.

        Returns:
            The data, when every key is defined.

        Raises:
            PydanticCustomError: Listing the (field, reason) problems.
        """
        if not isinstance(data, dict):
            return data
        keys = cast('dict[str, object]', data)
        known = {
            (field_info.alias or field_name) for field_name, field_info in cls.model_fields.items()
        }
        problems: list[tuple[str, str]] = []
        for key in keys:
            if key in known:
                continue
            if key in cls.arriving_later:
                problems.append((key, f'{key} arrives in {cls.arriving_later[key]}'))
            else:
                reason = f"unknown {cls.unknown_noun} '{key}'{_suggestion(key, sorted(known))}"
                problems.append((key, reason))
        if problems:
            raise PydanticCustomError(
                UNKNOWN_FIELDS_ERROR, UNKNOWN_FIELDS_MESSAGE, {'problems': tuple(problems)}
            )
        return keys


def _checked_pitch(value: object) -> PitchValue:
    """Check a pitch with the engine's own parser (a note name or a float in hertz).

    Returns:
        The pitch as written.

    Raises:
        ValueError: On a bare int, a bad note name or an unusable frequency.
    """
    try:
        resolve_pitch(
            cast('PitchLike', value), tuning=Tuning(), sample_rate=PITCH_VALIDATION_SAMPLE_RATE
        )
    except TypeError as error:
        message = f'a pitch is a note name or a float in hertz: {error}'
        raise ValueError(message) from None
    assert isinstance(value, str | float)  # resolve_pitch refuses every other accepted type
    return value


Pitch = Annotated[PitchValue, BeforeValidator(_checked_pitch)]


def _note_pairs(value: Sequence[object]) -> tuple[tuple[PitchValue, float], ...]:
    """Check an array of ``[pitch, seconds]`` pairs (a pitch of ``"_"`` is a rest).

    Returns:
        The pairs.

    Raises:
        ValueError: On an element that is not a pitch and a number of seconds.
    """
    pairs: list[tuple[PitchValue, float]] = []
    for pair in value:
        if not isinstance(pair, list) or len(cast('list[object]', pair)) != NOTE_PAIR_LENGTH:
            message = f'each note is [pitch, seconds], got {pair!r}'
            raise ValueError(message)
        pitch, seconds = cast('list[object]', pair)
        if not isinstance(seconds, int | float) or isinstance(seconds, bool):
            message = f'the seconds of a note must be a number, got {seconds!r}'
            raise ValueError(message)  # ruff: ignore[type-check-without-type-error] - pydantic reports ValueError
        pitch_value = REST_TOKEN if pitch == REST_TOKEN else _checked_pitch(pitch)
        pairs.append((pitch_value, float(seconds)))
    return tuple(pairs)


def _checked_notes(value: object) -> NoteList:
    """Check a melody: ``"B5:0.06 E6:0.18"`` or pairs of ``[pitch, seconds]``.

    Returns:
        The melody as a string or a tuple of pairs.

    Raises:
        ValueError: On a bad token, a bad pair, an empty melody or more than 256 notes.
    """
    notes: NoteList
    if isinstance(value, str):
        notes = value
        count = len(value.split())
    elif isinstance(value, list):
        notes = _note_pairs(cast('list[object]', value))
        count = len(notes)
    else:
        message = 'notes is a "pitch:seconds ..." string or an array of [pitch, seconds]'
        raise ValueError(message)  # ruff: ignore[type-check-without-type-error] - pydantic reports ValueError
    if count > MAXIMUM_NOTES:
        message = f'notes holds at most {MAXIMUM_NOTES} notes, got {count}'
        raise ValueError(message)
    parse_notes(notes, tuning=Tuning(), sample_rate=PITCH_VALIDATION_SAMPLE_RATE)
    return notes


Notes = Annotated[NoteList, BeforeValidator(_checked_notes)]


def _named_position(value: object, *, names: type, label: str) -> object:
    """Turn a lower-case ``CYCLE`` or ``LEVEL`` name into its number.

    Returns:
        The number the name stands for; anything else unchanged.

    Raises:
        ValueError: On a name that is not one of the class's.
    """
    if not isinstance(value, str):
        return value
    named = getattr(names, value.upper(), None)
    if not isinstance(named, float):
        known = sorted(
            name.lower() for name, member in vars(names).items() if isinstance(member, float)
        )
        message = f"unknown {label} '{value}'; use a number or one of {', '.join(known)}"
        raise ValueError(message)  # ruff: ignore[type-check-without-type-error] - pydantic reports ValueError
    return named


def _cycle_position(value: object) -> object:
    return _named_position(value, names=CYCLE, label='position')


def _level_height(value: object) -> object:
    return _named_position(value, names=LEVEL, label='level')


def _envelope_from_preset(value: object) -> object:
    """Let an envelope be a preset name or a table.

    Returns:
        The preset's fields for a name; anything else unchanged.

    Raises:
        ValueError: On a name that is not a preset.
    """
    if not isinstance(value, str):
        return value
    if value not in ENVELOPE_PRESETS:
        message = f'unknown envelope preset {value!r}; presets are {", ".join(ENVELOPE_PRESETS)}'
        raise ValueError(message)
    return asdict(ENVELOPE_PRESETS[value])


class BlendTable(_Table):
    """``blend = { from = name, to = name, amount = 0-1 }``."""

    source: str = Field(alias='from')
    to: str
    amount: Annotated[float, Field(ge=0.0, le=1.0)]


class PointTable(_Table):
    """One ``{ at, level }`` point; numbers or ``CYCLE``/``LEVEL`` names in lower case."""

    at: Annotated[float, BeforeValidator(_cycle_position), Field(ge=0.0, le=1.0)]
    level: Annotated[float, BeforeValidator(_level_height), Field(ge=-1.0, le=1.0)]


HarmonicLevel = Annotated[float, Field(ge=0.0, le=1.0)]


class HarmonicsTable(_Table):
    """``{ fundamental = 1.0, octave = 0.5 }`` or ``{ drawbars = "888000000" }``.

    Every named level is 0-1 and silent unless given.
    """

    drawbars: str | None = None
    fundamental: HarmonicLevel = 0.0
    octave: HarmonicLevel = 0.0
    octave_and_fifth: HarmonicLevel = 0.0
    two_octaves: HarmonicLevel = 0.0
    harmonic_5: HarmonicLevel = 0.0
    harmonic_6: HarmonicLevel = 0.0
    harmonic_7: HarmonicLevel = 0.0
    harmonic_8: HarmonicLevel = 0.0
    harmonic_9: HarmonicLevel = 0.0
    harmonic_10: HarmonicLevel = 0.0
    harmonic_11: HarmonicLevel = 0.0
    harmonic_12: HarmonicLevel = 0.0
    harmonic_13: HarmonicLevel = 0.0
    harmonic_14: HarmonicLevel = 0.0
    harmonic_15: HarmonicLevel = 0.0
    harmonic_16: HarmonicLevel = 0.0
    harmonic_17: HarmonicLevel = 0.0
    harmonic_18: HarmonicLevel = 0.0
    harmonic_19: HarmonicLevel = 0.0
    harmonic_20: HarmonicLevel = 0.0
    harmonic_21: HarmonicLevel = 0.0
    harmonic_22: HarmonicLevel = 0.0
    harmonic_23: HarmonicLevel = 0.0
    harmonic_24: HarmonicLevel = 0.0
    harmonic_25: HarmonicLevel = 0.0
    harmonic_26: HarmonicLevel = 0.0
    harmonic_27: HarmonicLevel = 0.0
    harmonic_28: HarmonicLevel = 0.0
    harmonic_29: HarmonicLevel = 0.0
    harmonic_30: HarmonicLevel = 0.0
    harmonic_31: HarmonicLevel = 0.0
    harmonic_32: HarmonicLevel = 0.0


class WaveTable(_Table):
    """A ``[waves.<name>]`` table: exactly one of mix, blend, harmonics or points."""

    mix: dict[str, float] | None = None
    blend: BlendTable | None = None
    harmonics: HarmonicsTable | None = None
    points: list[PointTable] | None = None
    shape: str = 'linear'
    normalize: bool = True

    @field_validator('shape')
    @classmethod
    def _known_shape(cls, value: str) -> str:
        if value not in POINT_SHAPES:
            message = f'unknown shape {value!r}; use {", ".join(POINT_SHAPES)}'
            raise ValueError(message)
        return value

    @model_validator(mode='after')
    def _one_kind(self) -> Self:
        kinds = [
            kind
            for kind in ('mix', 'blend', 'harmonics', 'points')
            if getattr(self, kind) is not None
        ]
        if len(kinds) != 1:
            message = 'a wave has exactly one of mix, blend, harmonics, points'
            raise ValueError(message)
        for point_only in ('shape', 'normalize'):
            if point_only in self.model_fields_set and kinds[0] != 'points':
                message = f'{point_only} applies only to a wave drawn with points'
                raise ValueError(message)
        return self


class EnvelopeTable(_Table):
    """``{ attack, decay, sustain, release, curve }`` in seconds."""

    attack: Annotated[float, Field(ge=0.0)]
    decay: Annotated[float, Field(ge=0.0)]
    sustain: Annotated[float, Field(ge=0.0, le=1.0)]
    release: Annotated[float, Field(ge=0.0)]
    curve: str = 'linear'

    @field_validator('curve')
    @classmethod
    def _known_curve(cls, value: str) -> str:
        if ENVELOPE_CURVE_PATTERN.fullmatch(value) is None:
            message = f'unknown envelope curve {value!r}; use linear, exponential or steps(n)'
            raise ValueError(message)
        return value

    def to_spec(self) -> EnvelopeSpec:
        """Convert to the spec form.

        Returns:
            The envelope spec.
        """
        return EnvelopeSpec(
            attack=self.attack,
            decay=self.decay,
            sustain=self.sustain,
            release=self.release,
            curve=self.curve,
        )


Envelope = Annotated[EnvelopeTable, BeforeValidator(_envelope_from_preset)]
OptionalEnvelope = Annotated[EnvelopeTable | None, BeforeValidator(_envelope_from_preset)]


class FilterTable(_Table):
    """``{ type = low_pass/high_pass, cutoff }`` (a FIR filter in M1)."""

    arriving_later: ClassVar[Mapping[str, str]] = FILTER_FIELDS_ARRIVING_LATER

    kind: str = Field(alias='type')
    cutoff: Annotated[float, Field(gt=0.0)]

    @field_validator('kind')
    @classmethod
    def _known_kind(cls, value: str) -> str:
        if value in FILTER_KINDS_ARRIVING_LATER:
            message = f'{value} arrives in {FILTER_KINDS_ARRIVING_LATER[value]}'
            raise ValueError(message)
        if value not in FILTER_KINDS:
            message = f'unknown filter type {value!r}; use {" or ".join(FILTER_KINDS)}'
            raise ValueError(message)
        return value

    def to_filter(self) -> Filter:
        """Convert to the instrument form.

        Returns:
            The filter.
        """
        return Filter(kind=self.kind, cutoff=self.cutoff)


class PitchCurveTable(_Table):
    """``{ to = pitch, seconds, easing = "linear" }``."""

    to: Pitch
    seconds: Annotated[float, Field(gt=0.0)]
    easing: str = 'linear'

    @field_validator('easing')
    @classmethod
    def _known_easing(cls, value: str) -> str:
        try:
            get_easing(value)
        except KeyError as error:
            raise ValueError(error.args[0]) from None
        return value


def _checked_lfsr_rate(value: object) -> PitchValue:
    return FOLLOW_THE_NOTE if value == FOLLOW_THE_NOTE else _checked_pitch(value)


class LfsrTable(_Table):
    """``{ bits = 15 or 7, taps = [a, b], rate }``."""

    bits: Annotated[int, Field(ge=1)] = 15
    taps: tuple[int, int] | None = None
    rate: Annotated[PitchValue, BeforeValidator(_checked_lfsr_rate)] = FOLLOW_THE_NOTE

    @model_validator(mode='after')
    def _maximal_length_taps(self) -> Self:
        if self.taps is not None:
            check_lfsr_taps(self.bits, self.taps)
        return self


class SourceTable(_Table):
    """A ``[instruments.<name>.sources.<source>]`` table: one layer of an instrument."""

    wave: str | None = None
    noise: str | None = None
    duty: Annotated[float | None, Field(ge=0.01, le=0.99)] = None
    lfsr: LfsrTable | None = None
    level: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    octave: float = 0.0
    semitones: float = 0.0
    detune_cents: float = 0.0
    pitch: Pitch | None = None
    pitch_curve: PitchCurveTable | None = None
    envelope: OptionalEnvelope = None
    filter: FilterTable | None = None

    @field_validator('noise')
    @classmethod
    def _known_noise(cls, value: str | None) -> str | None:
        if value is not None and value in NOISE_KINDS_ARRIVING_LATER:
            message = f'{value} arrives in {NOISE_KINDS_ARRIVING_LATER[value]}'
            raise ValueError(message)
        if value is not None and value not in NOISE_KINDS:
            message = f'unknown noise {value!r}; use {" or ".join(NOISE_KINDS)}'
            raise ValueError(message)
        return value

    @field_validator('duty')
    @classmethod
    def _duty_on_a_pulse(cls, value: float | None, info: ValidationInfo) -> float | None:
        if value is not None and info.data.get('wave') != 'pulse':
            message = 'duty only applies to the pulse wave (wave = "pulse")'
            raise ValueError(message)
        return value

    @field_validator('lfsr')
    @classmethod
    def _lfsr_on_lfsr_noise(cls, value: LfsrTable | None, info: ValidationInfo) -> LfsrTable | None:
        if value is not None and info.data.get('noise') != 'lfsr':
            message = 'lfsr applies only to noise = "lfsr"'
            raise ValueError(message)
        return value

    @model_validator(mode='after')
    def _one_content(self) -> Self:
        if (self.wave is None) == (self.noise is None):
            message = 'a source has exactly one of wave, noise'
            raise ValueError(message)
        return self


class InstrumentTable(_Table):
    """An ``[instruments.<name>]`` table (the M1 fields)."""

    profile: str = 'hybrid'
    envelope: Annotated[EnvelopeTable, BeforeValidator(_envelope_from_preset)] = Field(
        default='pluck',  # the validator turns the preset name into a table
        validate_default=True,
    )
    seed: int | None = None
    normalize: bool = False
    hard_edges: bool = False
    filter: FilterTable | None = None
    drive: Annotated[float, Field(ge=0.0, le=DRIVE_HIGHEST)] = 0.0
    sources: dict[str, SourceTable] = Field(default_factory=dict, validate_default=True)

    @field_validator('profile')
    @classmethod
    def _known_profile(cls, value: str) -> str:
        if value not in PROFILES:
            message = f'unknown profile {value!r}; use one of {", ".join(PROFILES)}'
            raise ValueError(message)
        return value

    @field_validator('sources')
    @classmethod
    def _one_to_four_sources(cls, value: dict[str, SourceTable]) -> dict[str, SourceTable]:
        if not value:
            message = (
                'an instrument needs at least one source ([instruments.<name>.sources.<source>])'
            )
            raise ValueError(message)
        if len(value) > MAXIMUM_SOURCES:
            message = f'an instrument has at most {MAXIMUM_SOURCES} sources, got {len(value)}'
            raise ValueError(message)
        return value


class SoundTable(_Table):
    """A ``[sounds.<name>]`` table: an instrument or recorded file plus identity and playback."""

    instrument: str | None = None
    file: str | None = None
    pitch: Pitch | None = None
    notes: Notes | None = None
    chord: list[Pitch] | None = Field(default=None, min_length=1, max_length=MAXIMUM_CHORD_PITCHES)
    length: Annotated[float | None, Field(gt=0.0)] = None
    transpose: float = 0.0
    bus: str = 'effects'
    volume: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    pan: Annotated[float, Field(ge=-1.0, le=1.0)] = 0.0
    priority: int = 50
    loop: bool = False

    @field_validator('bus')
    @classmethod
    def _known_bus(cls, value: str) -> str:
        if value not in DEFAULT_BUS_NAMES:
            message = f'unknown bus {value!r}; valid buses are {", ".join(DEFAULT_BUS_NAMES)}'
            raise ValueError(message)
        return value

    @model_validator(mode='after')
    def _consistent(self) -> Self:
        if (self.instrument is None) == (self.file is None):
            message = 'a sound has exactly one of instrument, file'
            raise ValueError(message)
        identity = [name for name in ('pitch', 'notes', 'chord') if getattr(self, name) is not None]
        if len(identity) > 1:
            message = (
                'pitch, notes and chord are mutually exclusive; use transpose to shift a notes '
                'or chord sound'
            )
            raise ValueError(message)
        if self.file is not None and (identity or self.length is not None or self.transpose):
            message = 'a recorded file takes no pitch, notes, chord, length or transpose'
            raise ValueError(message)
        if self.notes is not None and self.length is not None:
            message = 'length does not apply to notes; give each note its own seconds'
            raise ValueError(message)
        if self.transpose and not (self.notes is not None or self.chord is not None):
            message = 'transpose applies to notes and chord; for a single sound change the pitch'
            raise ValueError(message)
        return self


class HeaderTable(_Table):
    """The ``[glitchygames]`` header."""

    kind: str
    version: int

    @field_validator('kind')
    @classmethod
    def _sounds_kind(cls, value: str) -> str:
        if value != SOUND_FILE_KIND:
            message = f"kind must be '{SOUND_FILE_KIND}' for a sound file, got {value!r}"
            raise ValueError(message)
        return value

    @field_validator('version')
    @classmethod
    def _readable_version(cls, value: int) -> int:
        if value < CURRENT_SCHEMA_VERSION:
            message = (
                f'version {value} is not valid in a header (version {LEGACY_SCHEMA_VERSION} '
                'recipe files have no header)'
            )
            raise ValueError(message)
        # A version above the current one never gets here: the loader refuses it first
        return value


class DefinitionsTable(_Table):
    """A version 1 sound file's header, waves and instruments (stage 1 of loading).

    The ``[sounds.*]`` tables are kept raw: a sound is validated in stage 2, so a broken sound
    never breaks another file's reference to this file's instruments.
    """

    unknown_noun: ClassVar[str] = 'table'

    glitchygames: HeaderTable
    waves: dict[str, WaveTable] = Field(default_factory=dict)
    instruments: dict[str, InstrumentTable] = Field(default_factory=dict)
    sounds: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class SoundEntry:
    """One ``[sounds.<name>]`` table, or one v0 recipe.

    Attributes:
        name: The short name.
        instrument_reference: The ``instrument`` string as written, or None.
        instrument: The instrument it names (same file, or ``path#name``), or None.
        file: The resolved path of a recorded WAV/OGG sound, or None.
        pitch: A pitch (a note name or hertz), or None.
        notes: A melody (a string or pairs), or None.
        chord: Pitches played together, or None.
        length: Seconds per note or chord before release, or None for the default.
        transpose: Semitones to shift notes or a chord.
        playback_defaults: The playback defaults, overridable in ``.play()``.
        legacy_recipe: The v0 recipe, or None.
        source_path: The sound file that defines this entry.
    """

    name: str
    instrument_reference: str | None = None
    instrument: Instrument | None = None
    file: Path | None = None
    pitch: PitchValue | None = None
    notes: NoteList | None = None
    chord: tuple[PitchValue, ...] | None = None
    length: float | None = None
    transpose: float = 0.0
    playback_defaults: PlaybackDefaults = field(default_factory=PlaybackDefaults)
    legacy_recipe: SoundRecipe | None = None
    source_path: Path | None = None


@dataclass(frozen=True, slots=True)
class SoundFile:
    """A validated sound file.

    Attributes:
        path: The file's resolved path.
        version: 1, or 0 for a recipe file.
        waves: The ``[waves.*]`` tables, built, by name (registering them is the library's job).
        instruments: The ``[instruments.*]`` tables, built, by name.
        sounds: The ``[sounds.*]`` tables (or v0 recipes), by short name.
        modification_times: ``(path, mtime_ns)`` of this file and every file it took an instrument
            from; the cache is valid while none changed.
    """

    path: Path
    version: int
    waves: Mapping[str, Wave]
    instruments: Mapping[str, Instrument]
    sounds: Mapping[str, SoundEntry]
    modification_times: tuple[tuple[Path, int], ...]


@dataclass(frozen=True, slots=True)
class SoundLocation:
    """Where a short name is defined.

    Attributes:
        path: A ``.toml`` sound file, or a recorded ``.wav``/``.ogg`` file.
        table_name: The ``[sounds.<name>]`` (or recipe) name in the TOML file; None for a
            recorded file.
    """

    path: Path
    table_name: str | None

    @property
    def is_recorded_file(self) -> bool:
        """Whether this is a recorded WAV/OGG file rather than a table in a sound file."""
        return self.table_name is None


def is_path_reference(source: str) -> bool:
    """Whether a sound string is a path (feature spec 3.2): it has ``/``, ``#`` or a sound suffix.

    Args:
        source: The string a game passed to ``audio.sound``.

    Returns:
        True for a path, False for a short name.
    """
    return (
        '/' in source
        or INSTRUMENT_SEPARATOR in source
        or source.lower().endswith(PATH_REFERENCE_SUFFIXES)
    )


@dataclass(frozen=True, slots=True)
class _Problem:
    """One thing wrong with a file: a TOML path and the reason."""

    path: str
    reason: str


def _toml_path(location: Sequence[str | int]) -> str:
    """Render a pydantic ``loc`` as a TOML path (``instruments.pickup.sources[0]``).

    Returns:
        The path.
    """
    rendered = ''
    for part in location:
        if isinstance(part, int):
            rendered += f'[{part}]'
        else:
            rendered += f'.{part}' if rendered else part
    return rendered


def _joined(path: str, key: str) -> str:
    return f'{path}.{key}' if path else key


def _problems_from(error: ValidationError, prefix: tuple[str, ...] = ()) -> list[_Problem]:
    problems: list[_Problem] = []
    for detail in error.errors():
        path = _toml_path((*prefix, *detail['loc']))
        if detail['type'] == UNKNOWN_FIELDS_ERROR:
            problems.extend(
                _Problem(_joined(path, key), reason)
                for key, reason in (detail.get('ctx') or {})['problems']
            )
        else:
            problems.append(_Problem(path, detail['msg'].removeprefix('Value error, ')))
    return problems


def _asset_error(path: Path, problems: Sequence[_Problem]) -> SoundAssetError:
    lines = [f'{path}: {problem.path}: {problem.reason}' for problem in problems]
    return SoundAssetError('\n'.join(lines))


def _read_document(path: Path) -> dict[str, Any]:
    """Read a TOML file.

    Returns:
        The document.

    Raises:
        SoundAssetError: When the file cannot be read or is not valid TOML.
    """
    try:
        with path.open('rb') as sound_file:
            return tomllib.load(sound_file)
    except OSError as error:
        message = f'{path}: the file cannot be read: {error.strerror or error}'
        raise SoundAssetError(message) from error
    except tomllib.TOMLDecodeError as error:
        message = f'{path}: not valid TOML: {error}'
        raise SoundAssetError(message) from error


def _reference_path(boundary: Path, base_directory: Path, reference: str) -> Path | None:
    """Resolve a path written in a file, relative to the file's directory.

    Symlinks are followed, so a link that points outside the boundary escapes it.

    Returns:
        The resolved path, or None when it is absolute or leaves the boundary.
    """
    if Path(reference).is_absolute():
        return None
    resolved = (base_directory / reference).resolve()
    return resolved if resolved.is_relative_to(boundary.resolve()) else None


def _escape_reason(reference: str, boundary: Path) -> str:
    return f'{reference!r} escapes the game package {boundary}; use a relative path inside it'


def _wave_references(table: WaveTable) -> list[str]:
    if table.mix is not None:
        return list(table.mix)
    if table.blend is not None:
        return [table.blend.source, table.blend.to]
    return []


def _wave_from_table(table: WaveTable) -> Wave:
    """Build one wave; its references are already in the current wave registry.

    Returns:
        The wave.

    Raises:
        ValueError: From the wave constructors, naming what is wrong.
    """
    if table.mix is not None:
        return Wave.mix(**table.mix)
    if table.blend is not None:
        return current_wave_registry()[table.blend.source].blend(
            table.blend.to, amount=table.blend.amount
        )
    if table.harmonics is not None:
        levels = table.harmonics.model_dump()
        drawbars = levels.pop('drawbars')
        if drawbars is not None:
            if table.harmonics.model_fields_set - {'drawbars'}:
                message = 'drawbars cannot be combined with named harmonic levels'
                raise ValueError(message)
            return Wave.from_harmonics(Harmonics.drawbars(drawbars))
        return Wave.from_harmonics(Harmonics(**levels))
    assert table.points is not None  # WaveTable requires exactly one kind
    return Wave.from_points(
        [WavePoint(at=point.at, level=point.level) for point in table.points],
        shape=table.shape,
        normalize=table.normalize,
    )


class _WaveBuilder:
    """Builds a file's waves in dependency order, in a scratch engine context.

    A wave may mix or blend built-in waves, waves registered in the current context, and the
    file's own waves in any order. Building in a scratch context registers nothing: that is the
    library's job.
    """

    def __init__(self, tables: Mapping[str, WaveTable], problems: list[_Problem]) -> None:
        self._tables = tables
        self._problems = problems
        self._built: dict[str, Wave] = {}
        self._failed: set[str] = set()
        self._outer_registry = current_wave_registry()

    def build_all(self) -> dict[str, Wave]:
        """Build every wave that can be built.

        Returns:
            The waves that built; the reasons the others did not are in the problems.
        """
        with EngineContext(name='sound file waves').active():
            scratch_registry = current_wave_registry()
            for name in self._tables:
                self._build(name, (), scratch_registry)
        return self._built

    def _build(self, name: str, chain: tuple[str, ...], scratch_registry: WaveRegistry) -> bool:
        if name in self._built:
            return True
        if name in self._failed or name in chain:
            if name in chain:
                cycle = ' -> '.join((*chain[chain.index(name) :], name))
                self._problems.append(
                    _Problem(f'waves.{name}', f'circular wave references: {cycle}')
                )
            self._failed.add(name)
            return False
        table = self._tables[name]
        for reference in _wave_references(table):
            if not self._reference_ready(reference, (*chain, name), scratch_registry):
                self._failed.add(name)
                return False
        try:
            wave = _wave_from_table(table)
            scratch_registry.register(name, wave)
        except ValueError as error:
            where = f'waves.{name}.harmonics' if 'drawbars' in str(error) else f'waves.{name}'
            self._problems.append(_Problem(where, str(error)))
            self._failed.add(name)
            return False
        self._built[name] = wave
        return True

    def _reference_ready(
        self, reference: str, chain: tuple[str, ...], scratch_registry: WaveRegistry
    ) -> bool:
        if reference in self._tables:
            return self._build(reference, chain, scratch_registry)
        if reference not in BUILT_IN_WAVE_NAMES and reference in self._outer_registry:
            scratch_registry.register(reference, self._outer_registry[reference])
        return True


def _build_waves(tables: Mapping[str, WaveTable], problems: list[_Problem]) -> dict[str, Wave]:
    """Build the file's waves.

    Returns:
        The waves that built; the reasons the others did not are added to ``problems``.
    """
    return _WaveBuilder(tables, problems).build_all()


def _source_from_table(
    table: SourceTable, *, waves: Mapping[str, Wave], location: str, problems: list[_Problem]
) -> Source | None:
    """Build one source.

    Returns:
        The source, or None when its wave is unknown (the reason is added to ``problems``).
    """
    content: Wave | str | Noise
    if table.wave is not None:
        if table.wave in waves:
            content = waves[table.wave]
        elif table.duty is not None:
            content = Wave('pulse', duty=table.duty)
        elif table.wave in current_wave_registry():
            content = table.wave
        else:
            known = [*BUILT_IN_WAVE_NAMES, *waves]
            reason = f'unknown wave {table.wave!r}{_suggestion(table.wave, known)}'
            problems.append(_Problem(f'{location}.wave', reason))
            return None
    else:
        assert table.noise is not None  # SourceTable requires exactly one of wave, noise
        if table.lfsr is None:
            content = Noise(table.noise)
        else:
            content = Noise(
                table.noise,
                bits=table.lfsr.bits,
                taps=table.lfsr.taps,
                rate=None if table.lfsr.rate == FOLLOW_THE_NOTE else table.lfsr.rate,
            )
    return Source(
        content,
        level=table.level,
        semitones=table.semitones + table.octave * SEMITONES_PER_OCTAVE,
        detune_cents=table.detune_cents,
        pitch=table.pitch,
        pitch_curve=(
            PitchCurve(
                to=table.pitch_curve.to,
                seconds=table.pitch_curve.seconds,
                easing=table.pitch_curve.easing,
            )
            if table.pitch_curve is not None
            else None
        ),
        envelope=table.envelope.to_spec() if table.envelope is not None else None,
        filter=table.filter.to_filter() if table.filter is not None else None,
    )


def _build_instruments(
    tables: Mapping[str, InstrumentTable], *, waves: Mapping[str, Wave], problems: list[_Problem]
) -> dict[str, Instrument]:
    """Build the file's instruments.

    Returns:
        The instruments that built; the reasons the others did not are added to ``problems``.
    """
    instruments: dict[str, Instrument] = {}
    for name, table in tables.items():
        location = f'instruments.{name}'
        sources: dict[str, Source] = {}
        for source_name, source_table in table.sources.items():
            source = _source_from_table(
                source_table,
                waves=waves,
                location=f'{location}.sources.{source_name}',
                problems=problems,
            )
            if source is not None:
                sources[source_name] = source
        if len(sources) != len(table.sources):
            continue
        try:
            instruments[name] = Instrument(
                sources=sources,
                envelope=table.envelope.to_spec(),
                filter=table.filter.to_filter() if table.filter is not None else None,
                drive=table.drive,
                profile=table.profile,
                seed=table.seed,
                normalize=table.normalize,
                hard_edges=table.hard_edges,
            )
        except ValueError as error:  # pragma: no cover - the tables already enforce every rule
            problems.append(_Problem(location, str(error)))
    return instruments


type _CacheKey = tuple[Path, Path | None]

_CACHE: dict[_CacheKey, SoundFile] = {}
_DEFINITIONS_CACHE: dict[Path, _Definitions] = {}


def clear_sound_file_cache() -> None:
    """Forget every loaded sound file (for tests and tools)."""
    _CACHE.clear()
    _DEFINITIONS_CACHE.clear()


def _modification_time(path: Path) -> int:
    """Return a file's modification time in nanoseconds.

    Raises:
        SoundAssetError: When the file cannot be read.
    """
    try:
        return path.stat().st_mtime_ns
    except OSError as error:
        message = f'{path}: the file cannot be read: {error.strerror or error}'
        raise SoundAssetError(message) from error


def _still_current(sound_file: SoundFile) -> bool:
    """Whether none of the files a loaded file depends on has changed or gone.

    Returns:
        True while every dependency has the modification time it had at load.
    """
    for dependency, modification_time in sound_file.modification_times:
        try:
            if dependency.stat().st_mtime_ns != modification_time:
                return False
        except OSError:
            return False
    return True


def load_sound_file(path: Path, *, package_root: Path | None = None) -> SoundFile:
    """Read and validate a sound file (version 1) or recipe file (version 0).

    The result is cached by the file's resolved path, the package root and modification time
    (and those of the files it took instruments from), so loading a file again is a dictionary hit.

    Args:
        path: The ``.toml`` file.
        package_root: The game package's directory: paths in the file (``file``, ``path#name``)
            may point anywhere inside it. None confines them to the sound file's own directory.

    Returns:
        The validated file. Nothing is registered or compiled. A problem is a
        ``SoundAssetError`` naming the file, the TOML path of each problem and the reason.
    """
    resolved_root = package_root.resolve() if package_root is not None else None
    return _load(path.resolve(), package_root=resolved_root)


@dataclass(frozen=True, slots=True)
class _Definitions:
    """Stage 1 of loading a file: its header, waves and instruments, with no sounds resolved.

    ``tables`` is None for a version 0 file.
    """

    path: Path
    modification_time: int
    document: dict[str, Any]
    tables: DefinitionsTable | None
    waves: Mapping[str, Wave]
    instruments: Mapping[str, Instrument]


def _definitions(path: Path) -> _Definitions:
    """Load stage 1 of a file (cached by modification time).

    A sound in another file reaches an instrument through this stage only, so files that use each
    other's instruments cannot form a cycle.

    Returns:
        The definitions. A missing header, a newer version or a bad header, wave or instrument is
        a ``SoundAssetError``.
    """
    modification_time = _modification_time(path)
    cached = _DEFINITIONS_CACHE.get(path)
    if cached is not None and cached.modification_time == modification_time:
        return cached
    document = _read_document(path)
    if 'glitchygames' in document:
        found = _version_one_definitions(path, document, modification_time=modification_time)
    elif 'recipes' in document:
        found = _Definitions(
            path, modification_time, document, None, MappingProxyType({}), MappingProxyType({})
        )
    else:
        header_problem = _Problem(
            'glitchygames',
            'the [glitchygames] header table is missing; start the file with '
            f'kind = "{SOUND_FILE_KIND}" and version = {CURRENT_SCHEMA_VERSION}',
        )
        error = _asset_error(path, [header_problem])
        raise error
    _DEFINITIONS_CACHE[path] = found
    return found


def _version_one_definitions(
    path: Path, document: dict[str, Any], *, modification_time: int
) -> _Definitions:
    """Validate a version 1 file's header, waves and instruments.

    Returns:
        The definitions. Every problem found is listed in one ``SoundAssetError``.
    """
    header = document['glitchygames']
    version = cast('dict[str, object]', header).get('version') if isinstance(header, dict) else None
    if (
        isinstance(version, int)
        and not isinstance(version, bool)
        and version > CURRENT_SCHEMA_VERSION
    ):
        # A newer file may use fields this engine has never heard of, so say only this
        newer = _Problem(
            'glitchygames.version',
            f'version {version} is newer than this engine reads (version '
            f'{CURRENT_SCHEMA_VERSION}); update glitchygames',
        )
        error = _asset_error(path, [newer])
        raise error
    try:
        tables = DefinitionsTable.model_validate(document)
    except ValidationError as error:
        wrapped = _asset_error(path, _problems_from(error))
        raise wrapped from None
    problems: list[_Problem] = []
    waves = _build_waves(tables.waves, problems)
    instruments = _build_instruments(tables.instruments, waves=waves, problems=problems)
    if problems:
        error = _asset_error(path, problems)
        raise error
    return _Definitions(
        path,
        modification_time,
        document,
        tables,
        MappingProxyType(waves),
        MappingProxyType(instruments),
    )


def _load(path: Path, *, package_root: Path | None) -> SoundFile:
    """Load a file completely: stage 1, then its sounds (stage 2).

    Returns:
        The file, from the cache when it is current.
    """
    key = (path, package_root)
    cached = _CACHE.get(key)
    if cached is not None and _still_current(cached):
        return cached
    definitions = _definitions(path)
    if definitions.tables is None:
        sound_file = _load_version_zero(definitions)
    else:
        sound_file = _load_version_one(
            definitions, boundary=package_root if package_root is not None else path.parent
        )
    _CACHE[key] = sound_file
    return sound_file


def _warn_unknown_recipe_fields(path: Path, document: dict[str, Any]) -> None:
    """Warn about every field a version 0 file has that this engine does not read.

    Version 0 files are old and hand-edited, so unknown fields are logged and ignored
    (feature spec 9.3) rather than refused.
    """
    for key in document:
        if key != 'recipes':
            log.warning("%s: unknown table '%s' in a version 0 file is ignored", path, key)
    for name, recipe in document['recipes'].items():
        if not isinstance(recipe, dict):
            continue
        fields = cast('dict[str, Any]', recipe)
        for key in fields:
            if key not in LEGACY_RECIPE_FIELDS:
                log.warning("%s: unknown field 'recipes.%s.%s' is ignored", path, name, key)
        tones = fields.get('tones', [])
        if isinstance(tones, list):
            _warn_unknown_tone_fields(path, name, cast('list[Any]', tones))


def _warn_unknown_tone_fields(path: Path, recipe_name: str, tones: list[Any]) -> None:
    """Warn about every field of a version 0 recipe's tones that this engine does not read."""
    for index, tone in enumerate(tones):
        if not isinstance(tone, dict):
            continue
        for key in cast('dict[str, Any]', tone):
            if key not in LEGACY_TONE_FIELDS:
                log.warning(
                    "%s: unknown field 'recipes.%s.tones[%d].%s' is ignored",
                    path,
                    recipe_name,
                    index,
                    key,
                )


def _load_version_zero(definitions: _Definitions) -> SoundFile:
    """Load a ``[recipes.<name>]`` file: each recipe is a short name.

    Returns:
        The file, with a ``legacy_recipe`` entry per recipe. An invalid recipe, or a
        ``recipes`` that is not a table, is a ``SoundAssetError``.
    """
    path = definitions.path
    recipes = definitions.document['recipes']
    if not isinstance(recipes, dict):
        not_a_table = _Problem(
            'recipes',
            f'must be a table of recipes ([recipes.<name>]), got {type(recipes).__name__}',
        )
        error = _asset_error(path, [not_a_table])
        raise error
    _warn_unknown_recipe_fields(path, definitions.document)
    problems: list[_Problem] = []
    sounds: dict[str, SoundEntry] = {}
    for name, data in definitions.document['recipes'].items():
        try:
            recipe = SoundRecipe.from_dict(name, data)
        except (SoundRecipeError, KeyError, TypeError, ValueError, AttributeError) as error:
            problems.append(_Problem(f'recipes.{name}', f'{type(error).__name__}: {error}'))
            continue
        sounds[name] = SoundEntry(name=name, legacy_recipe=recipe, source_path=path)
    if problems:
        error = _asset_error(path, problems)
        raise error
    return SoundFile(
        path=path,
        version=LEGACY_SCHEMA_VERSION,
        waves=MappingProxyType({}),
        instruments=MappingProxyType({}),
        sounds=MappingProxyType(sounds),
        modification_times=((path, definitions.modification_time),),
    )


def _load_version_one(definitions: _Definitions, *, boundary: Path) -> SoundFile:
    """Resolve a version 1 file's sounds against its definitions.

    Returns:
        The file. Every problem found in the sounds is listed in one ``SoundAssetError``.
    """
    path = definitions.path
    assert definitions.tables is not None  # version 1 definitions carry their tables
    problems: list[_Problem] = []
    dependencies: dict[Path, int] = {path: definitions.modification_time}
    sounds: dict[str, SoundEntry] = {}
    for name, raw_table in definitions.tables.sounds.items():
        try:
            sound_table = SoundTable.model_validate(raw_table)
        except ValidationError as error:
            problems.extend(_problems_from(error, prefix=('sounds', name)))
            continue
        entry = _sound_entry(
            name,
            sound_table,
            path=path,
            boundary=boundary,
            instruments=definitions.instruments,
            dependencies=dependencies,
            problems=problems,
        )
        if entry is not None:
            sounds[name] = entry
    if problems:
        error = _asset_error(path, problems)
        raise error
    return SoundFile(
        path=path,
        version=CURRENT_SCHEMA_VERSION,
        waves=definitions.waves,
        instruments=definitions.instruments,
        sounds=MappingProxyType(sounds),
        modification_times=tuple(dependencies.items()),
    )


def _sound_entry(  # ruff: ignore[too-many-arguments] - one call site
    name: str,
    table: SoundTable,
    *,
    path: Path,
    boundary: Path,
    instruments: Mapping[str, Instrument],
    dependencies: dict[Path, int],
    problems: list[_Problem],
) -> SoundEntry | None:
    """Resolve one sound's instrument or recorded file.

    Returns:
        The entry, or None when its reference cannot be resolved (the reason is added to
        ``problems``).
    """
    location = f'sounds.{name}'
    if is_path_reference(name):
        problems.append(
            _Problem(
                location, f'the name {name!r} would be read as a path; avoid /, # and suffixes'
            )
        )
        return None
    instrument: Instrument | None = None
    recorded: Path | None = None
    if table.file is not None:
        recorded = _recorded_file(
            table.file,
            boundary=boundary,
            base=path.parent,
            location=f'{location}.file',
            problems=problems,
        )
        if recorded is None:
            return None
    else:
        assert table.instrument is not None  # SoundTable requires one of instrument, file
        instrument = _referenced_instrument(
            table.instrument,
            instruments=instruments,
            boundary=boundary,
            base=path.parent,
            location=f'{location}.instrument',
            dependencies=dependencies,
            problems=problems,
        )
        if instrument is None:
            return None
    return SoundEntry(
        name=name,
        instrument_reference=table.instrument,
        instrument=instrument,
        file=recorded,
        pitch=table.pitch,
        notes=table.notes,
        chord=tuple(table.chord) if table.chord is not None else None,
        length=table.length,
        transpose=table.transpose,
        playback_defaults=PlaybackDefaults(
            bus=table.bus,
            volume=table.volume,
            pan=table.pan,
            priority=table.priority,
            loop=table.loop,
        ),
        source_path=path,
    )


def _recorded_file(
    reference: str, *, boundary: Path, base: Path, location: str, problems: list[_Problem]
) -> Path | None:
    """Check a recorded sound's path and suffix (not that it exists: see ``require_recorded_file``).

    Returns:
        The resolved path, or None when it escapes the boundary or is not WAV/OGG.
    """
    resolved = _reference_path(boundary, base, reference)
    if resolved is None:
        reason = _escape_reason(reference, boundary)
    elif resolved.suffix.lower() not in RECORDED_SOUND_SUFFIXES:
        reason = f'{reference!r} must be a .wav or .ogg file'
    else:
        return resolved
    problems.append(_Problem(location, reason))
    return None


def require_recorded_file(entry: SoundEntry) -> Path:
    """Check that a recorded sound's file exists; the library calls this when the sound is compiled.

    A missing file is an error when the sound is first requested, not when its file loads, so one
    missing WAV never stops the file's other sounds.

    Args:
        entry: A ``SoundEntry`` with a ``file``.

    Returns:
        The file's path.

    Raises:
        SoundAssetError: Naming the file and ``sounds.<name>.file`` when the entry is not a
            recorded sound or the file does not exist.
    """
    where = f'{entry.source_path}: sounds.{entry.name}.file'
    if entry.file is None:
        message = f'{where}: the sound is not a recorded file'
        raise SoundAssetError(message)
    if not entry.file.is_file():
        message = f'{where}: {entry.file} does not exist'
        raise SoundAssetError(message)
    return entry.file


def _referenced_instrument(  # ruff: ignore[too-many-arguments] - one call site
    reference: str,
    *,
    instruments: Mapping[str, Instrument],
    boundary: Path,
    base: Path,
    location: str,
    dependencies: dict[Path, int],
    problems: list[_Problem],
) -> Instrument | None:
    """Find the instrument a sound names: this file's, or ``path#name`` in another file.

    Returns:
        The instrument, or None (the reason is added to ``problems``).
    """
    if INSTRUMENT_SEPARATOR in reference:
        found = _instrument_in_other_file(
            reference, boundary=boundary, base=base, dependencies=dependencies
        )
    elif reference in instruments:
        found = instruments[reference]
    else:
        known = list(instruments)
        listing = ', '.join(known) if known else 'none'
        found = (
            f'unknown instrument {reference!r}{_suggestion(reference, known)} '
            f'(this file defines: {listing})'
        )
    if isinstance(found, str):
        problems.append(_Problem(location, found))
        return None
    return found


def _instrument_in_other_file(
    reference: str, *, boundary: Path, base: Path, dependencies: dict[Path, int]
) -> Instrument | str:
    """Take ``path#name``'s instrument from the other file's stage 1.

    Returns:
        The instrument, or the reason it cannot be had.
    """
    file_part, _, instrument_name = reference.partition(INSTRUMENT_SEPARATOR)
    other_path = _reference_path(boundary, base, file_part)
    if other_path is None:
        return _escape_reason(file_part, boundary)
    try:
        other = _definitions(other_path)
    except SoundAssetError as error:
        return f'{file_part} cannot be used: {error}'
    dependencies[other_path] = other.modification_time
    if other.tables is None:
        return f'{other_path} is a version {LEGACY_SCHEMA_VERSION} file: it has no instruments'
    if instrument_name not in other.instruments:
        suggestion = _suggestion(instrument_name, list(other.instruments))
        return f'{other_path.name} has no instrument {instrument_name!r}{suggestion}'
    return other.instruments[instrument_name]


class ShortNameIndex:
    """Which file defines each short name, for one sound directory (feature spec 3.2).

    The index is built on the first ``resolve``: every ``.toml`` sound file in the directory is
    read for its ``[sounds.*]`` (or ``[recipes.*]``) table names, and every ``.wav``/``.ogg``
    file counts as a short name by its stem. Nothing is validated or compiled by indexing, and
    instruments are not indexed (a sound names an instrument in its own file or as
    ``path#name``). Other kinds of TOML file (sprites, levels) are skipped.
    """

    def __init__(self, directory: Path, *, package_root: Path | None = None) -> None:
        """Remember the directory; it is read on the first lookup.

        Args:
            directory: The sound directory.
            package_root: The game package's directory, passed to ``load_sound_file`` by
                ``load``; None confines each file's paths to its own directory.
        """
        self._directory = directory
        self._package_root = package_root
        self._locations: dict[str, list[SoundLocation]] | None = None

    @property
    def directory(self) -> Path:
        """The sound directory."""
        return self._directory

    def load(self, location: SoundLocation) -> SoundFile:
        """Load the sound file a resolved short name lives in.

        Args:
            location: A location from ``resolve`` (a ``.toml`` file, not a recorded file).

        Returns:
            The validated file.
        """
        return load_sound_file(location.path, package_root=self._package_root)

    def resolve(self, name: str) -> SoundLocation:
        """Find where a short name is defined.

        Args:
            name: The short name (``'coin'``, ``'sfx_slap'``).

        Returns:
            The ``.toml`` path and table name, or the recorded file's path.

        Raises:
            KeyError: When the directory is missing or defines no such name; the message names the
                directory and the close matches.
            SoundAssetError: When two files define the name (naming both).
        """
        locations = self._index()
        if name not in locations:
            known = sorted(locations)
            message = f'no sound named {name!r} in {self._directory}{_suggestion(name, known)}'
            raise KeyError(message)
        found = locations[name]
        if len(found) > 1:
            files = ' and '.join(str(location.path) for location in found)
            message = f'the short name {name!r} is defined in {files}; rename one'
            raise SoundAssetError(message)
        return found[0]

    def _index(self) -> dict[str, list[SoundLocation]]:
        """Build the index on first use.

        Returns:
            Short name to every place it is defined.

        Raises:
            KeyError: When the directory does not exist.
        """
        if self._locations is not None:
            return self._locations
        if not self._directory.is_dir():
            message = f'the sound directory {self._directory} does not exist'
            raise KeyError(message)
        locations: dict[str, list[SoundLocation]] = {}
        for entry in sorted(self._directory.iterdir()):
            suffix = entry.suffix.lower()
            if suffix == SOUND_FILE_SUFFIX:
                for table_name in _table_names(entry):
                    locations.setdefault(table_name, []).append(SoundLocation(entry, table_name))
            elif suffix in RECORDED_SOUND_SUFFIXES:
                locations.setdefault(entry.stem, []).append(SoundLocation(entry, None))
        self._locations = locations
        return locations


def _table_names(path: Path) -> list[str]:
    """Read the short names a TOML file defines; other kinds of file define none.

    Returns:
        The ``[sounds.*]`` names of a version 1 sound file, the recipe names of a version 0 file.
    """
    document = _read_document(path)
    header = document.get('glitchygames')
    if isinstance(header, dict):
        if cast('dict[str, object]', header).get('kind') != SOUND_FILE_KIND:
            return []
        sounds = document.get('sounds')
    elif 'recipes' in document:
        sounds = document['recipes']
    else:
        return []
    return list(cast('dict[str, object]', sounds)) if isinstance(sounds, dict) else []
