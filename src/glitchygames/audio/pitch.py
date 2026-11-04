"""Pitch types: notes, hertz, MIDI numbers and scale steps, and the one conversion to hertz.

Three explicit types name a pitch (``Note('A4')``, ``Hz(440.0)``, ``Midi(69)``), so a bare
``int`` is never guessed at: ``60`` could mean middle C or a 60 Hz hum. Anywhere a pitch is
accepted, a string is a note name and a float is hertz. ``resolve_pitch`` is the single point
that turns any of them into hertz.

Twelve-tone equal temperament is used: frequency = a4 * 2 ** ((midi_number - 69) / 12), the
standard MIDI tuning relation (https://en.wikipedia.org/wiki/MIDI_tuning_standard).
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Self, override

if TYPE_CHECKING:
    from collections.abc import Iterator

log: logging.Logger = logging.getLogger('game.audio.pitch')

SUPPORTED_LOW_HZ: Final[float] = 8.0
SUPPORTED_HIGH_HZ: Final[float] = 12000.0

MIDI_A4_NUMBER: Final[int] = 69
MIDI_LOWEST: Final[int] = 0
MIDI_HIGHEST: Final[int] = 127
SEMITONES_PER_OCTAVE: Final[int] = 12
CENTS_PER_SEMITONE: Final[float] = 100.0
DEFAULT_SCALE_ROOT_OCTAVE: Final[int] = 4
CENTS_TOLERANCE: Final[float] = 1e-9  # Float noise below this is treated as no offset

NOTE_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r'^([A-G])(#|b)?(-?\d)$')
PITCH_CLASS_PATTERN: Final[re.Pattern[str]] = re.compile(r'^([A-G])(#|b)?$')

LETTER_SEMITONES: Final[dict[str, int]] = {
    'C': 0,
    'D': 2,
    'E': 4,
    'F': 5,
    'G': 7,
    'A': 9,
    'B': 11,
}
ACCIDENTAL_SEMITONES: Final[dict[str | None, int]] = {None: 0, '#': 1, 'b': -1}
SHARP_NAMES: Final[tuple[str, ...]] = (
    'C',
    'C#',
    'D',
    'D#',
    'E',
    'F',
    'F#',
    'G',
    'G#',
    'A',
    'A#',
    'B',
)

# Semitone offsets from the root, one octave's worth, per scale kind.
SCALE_INTERVALS: Final[dict[str, tuple[int, ...]]] = {
    'major': (0, 2, 4, 5, 7, 9, 11),
    'minor': (0, 2, 3, 5, 7, 8, 10),
    'major_pentatonic': (0, 2, 4, 7, 9),
    'minor_pentatonic': (0, 3, 5, 7, 10),
    'blues': (0, 3, 5, 6, 7, 10),
    'chromatic': (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
    'whole_tone': (0, 2, 4, 6, 8, 10),
    'dorian': (0, 2, 3, 5, 7, 9, 10),
    'mixolydian': (0, 2, 4, 5, 7, 9, 10),
}

# Out-of-range values already warned about, so each distinct value warns once.
_warned_hertz_values: set[float] = set()


@dataclass(frozen=True)
class Tuning:
    """Equal-temperament tuning, set by the frequency of A4.

    Attributes:
        a4: The frequency of A4 in hertz.

    """

    a4: float = 440.0

    def __post_init__(self) -> None:
        """Validate the tuning.

        Raises:
            ValueError: If a4 is not a finite number above zero.

        """
        if not math.isfinite(self.a4) or self.a4 <= 0.0:
            message = f'Tuning a4 must be a finite number above zero, got {self.a4!r}'
            raise ValueError(message)

    def hertz_for_midi_number(self, midi_number: float) -> Hz:
        """Convert a (possibly fractional) MIDI note number to hertz.

        Args:
            midi_number: The MIDI note number; 69 is A4.

        Returns:
            The frequency in hertz.

        """
        return Hz(self.a4 * 2.0 ** ((midi_number - MIDI_A4_NUMBER) / SEMITONES_PER_OCTAVE))


class Hz(float):
    """A frequency in hertz."""

    __slots__ = ()

    def times(self, ratio: float) -> Hz:
        """Multiply the frequency by a ratio.

        Args:
            ratio: The factor; 1.5 is a perfect fifth in just intonation.

        Returns:
            The scaled frequency.

        """
        return Hz(float(self) * ratio)

    def octave_up(self, octaves: int = 1) -> Hz:
        """Raise the frequency by whole octaves.

        Args:
            octaves: The number of octaves.

        Returns:
            The frequency, doubled once per octave.

        """
        return self.times(2.0**octaves)

    def octave_down(self, octaves: int = 1) -> Hz:
        """Lower the frequency by whole octaves.

        Args:
            octaves: The number of octaves.

        Returns:
            The frequency, halved once per octave.

        """
        return self.times(2.0**-octaves)


class Midi(int):
    """A MIDI note number from 0 to 127; 60 is middle C and 69 is A4."""

    __slots__ = ()

    def __new__(cls, number: int) -> Self:
        """Create a MIDI note number.

        Args:
            number: The note number, 0 to 127.

        Returns:
            The validated MIDI note number.

        Raises:
            ValueError: If the number is not an int or is outside 0 to 127.

        """
        if isinstance(number, bool) or not isinstance(number, int):  # pyright: ignore[reportUnnecessaryIsInstance] - callers may pass anything at runtime
            message = f'Midi needs an int from 0 to 127, got {number!r}'
            raise ValueError(message)  # ruff: ignore[type-check-without-type-error] - contract is ValueError
        if not MIDI_LOWEST <= number <= MIDI_HIGHEST:
            message = f'Midi must be from {MIDI_LOWEST} to {MIDI_HIGHEST}, got {number}'
            raise ValueError(message)
        return super().__new__(cls, number)

    def to_hz(self, *, tuning: Tuning | None = None) -> Hz:
        """Convert to hertz.

        Args:
            tuning: The tuning to use; A4 = 440 Hz when omitted.

        Returns:
            The frequency in hertz.

        """
        return (tuning or Tuning()).hertz_for_midi_number(int(self))


class Note:
    """A note name such as 'C4', 'F#4' or 'Bb3', optionally shifted by cents.

    C4 is middle C and A4 is 440 Hz (at the default tuning). Shifts made by up, down and
    detune stay symbolic: the tuning is applied only when the note is converted to hertz, so
    a detuned note follows the engine's tuning. Notes compare and hash by pitch and offset, so
    'Bb3' equals 'A#3'.
    """

    __slots__ = ('_cents', '_midi_number', '_name')

    def __init__(self, name: str, *, cents: float = 0.0) -> None:
        """Parse a note name.

        Args:
            name: A letter A-G, an optional '#' or 'b', then an octave digit (optionally
                negative, so 'C-1' is MIDI 0).
            cents: An offset from the named note in hundredths of a semitone.

        Raises:
            ValueError: If the name is not a valid note name or cents is not finite.

        """
        match = NOTE_NAME_PATTERN.match(name) if isinstance(name, str) else None  # pyright: ignore[reportUnnecessaryIsInstance] - callers may pass anything at runtime
        if match is None:
            message = f"Invalid note name {name!r}; expected e.g. 'C4', 'F#4' or 'Bb3'"
            raise ValueError(message)
        if not math.isfinite(cents):
            message = f'Note cents must be finite, got {cents!r}'
            raise ValueError(message)
        letter, accidental, octave = match.groups()
        self._name: str = name
        self._cents: float = float(cents)
        self._midi_number: int = (
            SEMITONES_PER_OCTAVE * (int(octave) + 1)
            + LETTER_SEMITONES[letter]
            + ACCIDENTAL_SEMITONES[accidental]
        )

    @classmethod
    def from_midi_number(cls, midi_number: int, *, cents: float = 0.0) -> Note:
        """Build the note (spelled with sharps) for a MIDI note number.

        Args:
            midi_number: The note number; 60 is C4. It may lie outside 0 to 127, as long as
                the octave stays a single digit.
            cents: An offset from the note in hundredths of a semitone.

        Returns:
            The note.

        """
        octave, pitch_class = divmod(midi_number, SEMITONES_PER_OCTAVE)
        return cls(f'{SHARP_NAMES[pitch_class]}{octave - 1}', cents=cents)

    @property
    def name(self) -> str:
        """The name this note was created with."""
        return self._name

    @property
    def midi_number(self) -> int:
        """The MIDI note number of the named note, before any cents offset."""
        return self._midi_number

    @property
    def cents(self) -> float:
        """The offset from the named note in cents; 0.0 for a plain note."""
        return self._cents

    def up(self, *, semitones: float = 0.0, cents: float = 0.0) -> Note:
        """Move up in pitch, staying relative to whatever tuning is applied later.

        Args:
            semitones: Semitones to move up.
            cents: Hundredths of a semitone to move up.

        Returns:
            A note; a plain named note when the total shift is a whole number of semitones,
            otherwise the nearest named note carrying the remaining cents offset.

        """
        total_cents = self._cents + semitones * CENTS_PER_SEMITONE + cents
        whole_semitones = round(total_cents / CENTS_PER_SEMITONE)
        remaining_cents = total_cents - whole_semitones * CENTS_PER_SEMITONE
        if math.isclose(remaining_cents, 0.0, abs_tol=CENTS_TOLERANCE):
            remaining_cents = 0.0
        return Note.from_midi_number(
            self._midi_number + whole_semitones,
            cents=remaining_cents,
        )

    def down(self, *, semitones: float = 0.0, cents: float = 0.0) -> Note:
        """Move down in pitch.

        Args:
            semitones: Semitones to move down.
            cents: Hundredths of a semitone to move down.

        Returns:
            The lowered note; see up.

        """
        return self.up(semitones=-semitones, cents=-cents)

    def detune(self, *, cents: float) -> Note:
        """Shift slightly sharp (positive) or flat (negative).

        Args:
            cents: Hundredths of a semitone.

        Returns:
            The detuned note; see up.

        """
        return self.up(cents=cents)

    def to_hz(self, *, tuning: Tuning | None = None) -> Hz:
        """Convert to hertz: the tuning is applied first, then the cents offset.

        Args:
            tuning: The tuning to use; A4 = 440 Hz when omitted.

        Returns:
            The frequency in hertz.

        """
        return (tuning or Tuning()).hertz_for_midi_number(
            self._midi_number + self._cents / CENTS_PER_SEMITONE,
        )

    @override
    def __eq__(self, other: object) -> bool:
        """Compare by pitch and cents offset.

        Returns:
            True if other is a Note of the same pitch and offset.

        """
        if not isinstance(other, Note):
            return NotImplemented
        return (self._midi_number, self._cents) == (other._midi_number, other._cents)

    @override
    def __hash__(self) -> int:
        """Hash by pitch and cents offset.

        Returns:
            The hash of the MIDI note number and offset.

        """
        return hash(('Note', self._midi_number, self._cents))

    @override
    def __repr__(self) -> str:
        """Return a constructor-style representation.

        Returns:
            The representation.

        """
        if self._cents:
            return f'Note({self._name!r}, cents={self._cents!r})'
        return f'Note({self._name!r})'


@dataclass(frozen=True)
class Scale:
    """A scale from a root pitch class, played in numbered steps.

    Step 0 is the root in octave 4, and a step past the top wraps into the next octave.

    Attributes:
        root: The root pitch class, e.g. 'C', 'F#' or 'Bb'.
        kind: One of the names in SCALE_INTERVALS.

    """

    root: str
    kind: str

    def __post_init__(self) -> None:
        """Validate the root and kind.

        Raises:
            ValueError: If the root or the kind is not recognised.

        """
        if not isinstance(self.root, str) or PITCH_CLASS_PATTERN.match(self.root) is None:  # pyright: ignore[reportUnnecessaryIsInstance] - callers may pass anything at runtime
            message = f"Invalid scale root {self.root!r}; expected e.g. 'C', 'F#' or 'Bb'"
            raise ValueError(message)
        if self.kind not in SCALE_INTERVALS:
            message = f'Unknown scale {self.kind!r}; expected one of {sorted(SCALE_INTERVALS)}'
            raise ValueError(message)

    def step(self, number: int) -> Note:
        """Return the note at a numbered step.

        Args:
            number: The step; 0 is the root, negative steps go below it.

        Returns:
            The note.

        """
        intervals = SCALE_INTERVALS[self.kind]
        octaves, index = divmod(number, len(intervals))
        root_note = Note(f'{self.root}{DEFAULT_SCALE_ROOT_OCTAVE}')
        return Note.from_midi_number(
            root_note.midi_number + SEMITONES_PER_OCTAVE * octaves + intervals[index],
        )


@dataclass(frozen=True)
class ScaleStep:
    """A scale step kept lazily, resolved to a Note only when the pitch is needed.

    Attributes:
        scale: The scale.
        number: The step number within the scale.

    """

    scale: Scale
    number: int

    def to_note(self) -> Note:
        """Resolve the step.

        Returns:
            The note at this step.

        """
        return self.scale.step(self.number)


class PitchTable(Mapping[str, Hz]):
    """A game's own table of named frequencies, e.g. {'C4': 261.63}; lookups return Hz."""

    def __init__(self, table: Mapping[str, Hz]) -> None:
        """Wrap an already converted table; prefer from_dict.

        Args:
            table: Names mapped to frequencies.

        """
        self._table: dict[str, Hz] = dict(table)

    @classmethod
    def from_dict(cls, table: Mapping[str, float]) -> PitchTable:
        """Make a table from names and plain floats.

        Args:
            table: Names mapped to frequencies in hertz.

        Returns:
            The table; each value is stored unchanged as an Hz.

        """
        return cls({name: Hz(frequency) for name, frequency in table.items()})

    @override
    def __getitem__(self, name: str) -> Hz:
        """Look up a name.

        Returns:
            The frequency.

        """
        return self._table[name]

    @override
    def __iter__(self) -> Iterator[str]:
        """Iterate over the names.

        Returns:
            An iterator over the names.

        """
        return iter(self._table)

    @override
    def __len__(self) -> int:
        """Count the names.

        Returns:
            The number of names.

        """
        return len(self._table)


PitchLike = Note | Hz | Midi | ScaleStep | str | float


def _validated_hertz(frequency: float, *, sample_rate: int) -> Hz:
    """Check a frequency against Nyquist and warn once if outside the supported range.

    Args:
        frequency: The frequency in hertz.
        sample_rate: The sample rate used for the Nyquist limit.

    Returns:
        The frequency as Hz.

    Raises:
        ValueError: If the frequency is not finite, is negative, or is above Nyquist.

    """
    nyquist = sample_rate / 2.0
    if not math.isfinite(frequency) or frequency < 0.0 or frequency > nyquist:
        message = (
            f'Frequency {frequency!r} Hz must be finite and between 0 and the Nyquist '
            f'frequency {nyquist} Hz'
        )
        raise ValueError(message)
    outside_supported_range = not SUPPORTED_LOW_HZ <= frequency <= SUPPORTED_HIGH_HZ
    if outside_supported_range and frequency not in _warned_hertz_values:
        _warned_hertz_values.add(frequency)
        log.warning(
            'Pitch %s Hz is outside the supported %s-%s Hz range',
            frequency,
            SUPPORTED_LOW_HZ,
            SUPPORTED_HIGH_HZ,
        )
    return Hz(frequency)


def resolve_pitch(pitch: PitchLike, *, tuning: Tuning, sample_rate: int = 44100) -> Hz:
    """Convert any pitch to hertz; the one conversion point.

    Args:
        pitch: A Note, Hz, Midi, ScaleStep, a note-name string, or a float (hertz).
        tuning: The tuning for note names, MIDI numbers and scale steps.
        sample_rate: The sample rate, for the Nyquist check.

    Returns:
        The frequency in hertz.

    Raises:
        ValueError: For a bare int (use Midi or Hz), a bad note name, or a frequency that is
            not finite, is negative or is above Nyquist.
        TypeError: For any other type.

    """
    if isinstance(pitch, bool) or (isinstance(pitch, int) and not isinstance(pitch, Midi)):
        message = (
            f'A bare int is ambiguous: {pitch!r} could be a MIDI note or a frequency. '
            f'Use Midi({pitch}) or Hz({pitch}).'
        )
        raise ValueError(message)  # ruff: ignore[type-check-without-type-error] - contract is ValueError
    if isinstance(pitch, ScaleStep):
        pitch = pitch.to_note()
    if isinstance(pitch, str):
        pitch = Note(pitch)
    if isinstance(pitch, Note | Midi):
        return _validated_hertz(pitch.to_hz(tuning=tuning), sample_rate=sample_rate)
    if isinstance(pitch, float):  # pyright: ignore[reportUnnecessaryIsInstance] - callers may pass anything at runtime
        return _validated_hertz(float(pitch), sample_rate=sample_rate)
    message = f'Cannot use {pitch!r} of type {type(pitch).__name__} as a pitch'
    raise TypeError(message)
