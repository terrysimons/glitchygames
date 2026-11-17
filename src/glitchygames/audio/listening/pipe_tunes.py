"""Play public-domain tunes written in ABC notation on the pipe instruments (``pipes``).

Moved from ``scripts/pipe_tunes.py`` (plans/2026-11-14-sound-cache-on-first-use.md, decision 5),
its tunes with it: ``tunes/`` holds ``index.json`` (title, file, instrument, tempo per tune, and
each tune's source and why it is public domain) and the ``.abc`` files.
``glitchygames listening-pipes`` writes each tune to ``pipes/tunes/<file stem>.wav`` in the
listening folder (glitchygames/audio/listening/files.py).

The ABC reader covers the subset traditional-tune transcriptions use: the X/T/M/L/K/Q headers,
keys with modes, notes with octave marks and accidentals (accidentals last to the end of the bar),
lengths (``3``, ``/2``, ``3/2``, ``/``), rests, ties, triplets ``(3``, broken rhythm ``>`` and
``<``, bar lines, ``|: :|`` repeats and ``[1``/``[2`` (or ``|1``/``|2``) endings. Chord symbols,
grace notes, decorations and comments are skipped. ABC is described at
https://abcnotation.com/wiki/abc:standard:v2.1.

Arranging: a Scottish tune that fits goes on the Highland pipes (its A sounds at the chanter's
480 Hz, with high-G grace notes between repeated notes), anything else on the uilleann pipes, moved
to the uilleann chanter's D family (relative major D or G) and into its two-octave range, with
drones in D and regulator chords on the beats that follow each bar's first.
"""

from __future__ import annotations

import json
import math
import operator
import re
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, TypeGuard

from pydantic import BaseModel, ConfigDict, Field

from glitchygames.audio import Hz
from glitchygames.audio.listening.pipes import (
    HIGHLAND_GRACE_SECONDS,
    HIGHLAND_SCALE,
    HIGHLAND_TENOR_DRONE_HZ,
    SAMPLE_RATE,
    UILLEANN_REGULATOR_STAB_SECONDS,
    highland_chanter,
    highland_drones,
    mix,
    render,
    uilleann_chanter,
    uilleann_drones,
    uilleann_regulators,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    import numpy as np
    import numpy.typing as npt

# The tunes and their index ship with the engine, beside this module
TUNES_DIRECTORY = Path(__file__).parent / 'tunes'
TUNES_INDEX_FILE = 'index.json'

# --- ABC reading ------------------------------------------------------------------------------

LETTER_SEMITONES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
SHARP_ORDER = 'FCGDAEB'
MAJOR_KEY_SHARPS = {
    'C': 0,
    'G': 1,
    'D': 2,
    'A': 3,
    'E': 4,
    'B': 5,
    'F#': 6,
    'C#': 7,
    'F': -1,
    'Bb': -2,
    'Eb': -3,
    'Ab': -4,
    'Db': -5,
    'Gb': -6,
    'Cb': -7,
}
# How far each mode's tonic sits above its relative major's tonic, in semitones
MODE_OFFSETS = {
    'maj': 0,
    'ion': 0,
    'mix': 7,
    'dor': 2,
    'min': 9,
    'm': 9,
    'aeo': 9,
    'phr': 4,
    'lyd': 5,
    'loc': 11,
}
NOTE_NAMES_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B']
ACCIDENTAL_SHIFTS = {'^': 1, '^^': 2, '_': -1, '__': -2, '=': 0}  # ABC accidental -> semitones
SECOND_ENDING = 2  # the ``[2`` volta bracket
EIGHTH_NOTE_DENOMINATOR = 8  # 6/8, 9/8 and 12/8 are written in eighths
EIGHTHS_PER_COMPOUND_BEAT = 3  # a compound meter's beat is a dotted quarter: three eighths
DUPLET_COUNT = 2  # ``(2``: two notes in the time of three
TRIPLET_COUNT = 3  # ``(3``: three notes in the time of two
DUPLET_SCALE = Fraction(3, 2)
TRIPLET_SCALE = Fraction(2, 3)


class Note(BaseModel):
    """One sounding note or rest.

    Attributes:
        midi: Its MIDI number; None for a rest.
        whole_notes: Its length in whole notes.
        tied_to_next: Whether it is tied to the next note.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    midi: int | None
    whole_notes: Fraction
    tied_to_next: bool = False


class NoteToken(BaseModel):
    """A note or rest in a tune's body."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    note: Note


class BarToken(BaseModel):
    """A bar line in a tune's body, as written (``|``, ``|:``, ``:|``, ``::``...)."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    text: str


class EndingToken(BaseModel):
    """A ``[1`` or ``[2`` ending bracket in a tune's body."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    number: int


# One token of a tune's body
type Token = NoteToken | BarToken | EndingToken


class Tune(BaseModel):
    """A tune read from ABC: its meter and key, and its bars in playing order.

    Attributes:
        title: Its title (the T: header).
        meter: A bar's length in whole notes.
        beats_per_bar: 2 for 6/8, 3 for 9/8 and 3/4, 4 for 4/4 (compound meters count dotted
            beats).
        compound: Whether the beat is a dotted quarter (6/8, 9/8, 12/8).
        relative_major_pitch_class: Its key's relative major, as a pitch class.
        key_signature: The key signature's accidental for each letter.
        bars: Its bars in playing order.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    title: str
    meter: Fraction  # a bar's length in whole notes
    # 2 for 6/8, 3 for 9/8 and 3/4, 4 for 4/4 (compound meters count dotted beats)
    beats_per_bar: int
    compound: bool  # 6/8, 9/8, 12/8: the beat is a dotted quarter
    relative_major_pitch_class: int
    key_signature: dict[str, int]
    bars: list[list[Note]]


def key_signature(key_field: str) -> tuple[dict[str, int], int]:
    """The per-letter accidentals of an ABC K: field, and its relative major's pitch class.

    Args:
        key_field: The text of the K: header, such as ``D``, ``Gmix`` or ``Ador``.

    Returns:
        The accidental (-1, 0 or 1) of each letter A to G, and the relative major's pitch class.

    Raises:
        ValueError: The key is unreadable or names an unknown mode.
    """
    match = re.match(r'\s*([A-G])([#b]?)\s*([A-Za-z]*)', key_field)
    if match is None:
        message = f'unreadable key {key_field!r}'
        raise ValueError(message)
    letter, accidental, mode_text = match.groups()
    mode = mode_text.lower()[:3] if mode_text.lower() != 'm' else 'm'
    offset = MODE_OFFSETS.get(mode or 'maj')
    if offset is None:
        message = f'unknown mode {mode_text!r} in key {key_field!r}'
        raise ValueError(message)
    tonic = (LETTER_SEMITONES[letter] + {'#': 1, 'b': -1, '': 0}[accidental]) % 12
    relative_major = (tonic - offset) % 12
    candidates = [
        name
        for name in MAJOR_KEY_SHARPS
        if (LETTER_SEMITONES[name[0]] + {'#': 1, 'b': -1}.get(name[1:], 0)) % 12 == relative_major
    ]
    major = min(candidates, key=lambda name: abs(MAJOR_KEY_SHARPS[name]))
    count = MAJOR_KEY_SHARPS[major]
    signature = dict.fromkeys('ABCDEFG', 0)
    if count > 0:
        for sharp in SHARP_ORDER[:count]:
            signature[sharp] = 1
    else:
        for flat in SHARP_ORDER[::-1][:-count]:
            signature[flat] = -1
    return signature, relative_major


def parse_fraction(text: str) -> Fraction:
    """An ABC length (``3``, ``/2``, ``3/2``, ``/``; empty for 1) as a fraction.

    Args:
        text: The length text that followed a note or the L: header.

    Returns:
        The length as a multiple of the unit.
    """
    if not text:
        return Fraction(1)
    if text.startswith('/'):
        slashes = len(text) - len(text.lstrip('/'))
        rest = text[slashes:]
        denominator = int(rest) if rest else 2**slashes
        return Fraction(1, denominator)
    if '/' in text:
        numerator, _, denominator = text.partition('/')
        return Fraction(int(numerator), int(denominator) if denominator else 2)
    return Fraction(int(text))


NOTE_PATTERN = re.compile(r"(\^\^|\^|__|_|=)?([A-Ga-gz])([',]*)(\d*/*\d*)(-?)")


def _strip_annotations(body: str) -> str:
    """Drop chord symbols, grace notes, decorations and comments.

    Returns:
        The body with those removed.
    """
    body = re.sub(r'"[^"]*"', '', body)  # chord symbols
    body = re.sub(r'\{[^}]*\}', '', body)  # grace notes
    body = re.sub(r'![^!]*!|\+[^+]*\+', '', body)  # decorations
    return re.sub(r'%[^\n]*', '', body)  # comments


class _BodyState(BaseModel):
    """What parse_body carries from one token to the next (changed as it reads)."""

    model_config = ConfigDict(extra='forbid')

    unit: Fraction
    signature: dict[str, int]
    tokens: list[Token] = Field(default_factory=list)
    bar_accidentals: dict[tuple[str, int], int] = Field(default_factory=dict)
    triplet_left: int = 0
    triplet_scale: Fraction = Fraction(1)
    pending_broken: str | None = None


def _read_bar(body: str, position: int, state: _BodyState) -> int | None:
    """Read a bar line (and an ending bracket right after it).

    Returns:
        The position after it, or None if there is no bar line here.
    """
    bar_match = re.match(r':*\|[\]|]?:*|:{2,}|\[\|', body[position:])
    if not (bar_match and bar_match.group(0)):
        return None
    text = bar_match.group(0)
    position += len(text)
    ending = re.match(r'\[?([12])', body[position:])
    state.tokens.append(BarToken(text=text))
    state.bar_accidentals.clear()
    if ending:
        state.tokens.append(EndingToken(number=int(ending.group(1))))
        position += len(ending.group(0))
    return position


def _read_ending(body: str, position: int, state: _BodyState) -> int | None:
    """Read a ``[1`` or ``[2`` ending bracket.

    Returns:
        The position after it, or None if there is no ending bracket here.
    """
    ending = re.match(r'\[([12])', body[position:])
    if not ending:
        return None
    state.tokens.append(EndingToken(number=int(ending.group(1))))
    return position + len(ending.group(0))


def _tuplet_scale(count: int) -> Fraction:
    """How much a note shrinks inside a ``(count`` tuplet.

    Returns:
        The length scale applied to each note of the tuplet.
    """
    if count == TRIPLET_COUNT:
        return TRIPLET_SCALE
    if count == DUPLET_COUNT:
        return DUPLET_SCALE
    return Fraction(count - 1, count)


def _read_triplet(body: str, position: int, state: _BodyState) -> int | None:
    """Read a ``(3`` style tuplet marker.

    Returns:
        The position after it, or None if there is no tuplet marker here.
    """
    triplet = re.match(r'\((\d)', body[position:])
    if not triplet:
        return None
    count = int(triplet.group(1))
    state.triplet_left = count
    state.triplet_scale = _tuplet_scale(count)
    return position + len(triplet.group(0))


def _read_broken_rhythm(body: str, position: int, state: _BodyState) -> int | None:
    """Read a ``<`` or ``>`` broken rhythm marker.

    Returns:
        The position after it, or None if there is no marker here.
    """
    character = body[position]
    if character not in '<>':
        return None
    state.pending_broken = character
    return position + 1


def _apply_broken_rhythm(state: _BodyState, length: Fraction) -> Fraction:
    """Split the previous note and this one by the pending broken rhythm.

    Returns:
        This note's new length.
    """
    # broken rhythm: the previous note takes 3/4 (or 1/4) of the pair, this one the rest
    last = state.tokens[-1]
    if isinstance(last, NoteToken):
        last_note = last.note
        total = last_note.whole_notes + length
        first = total * (Fraction(3, 4) if state.pending_broken == '>' else Fraction(1, 4))
        state.tokens[-1] = NoteToken(
            note=Note(midi=last_note.midi, whole_notes=first, tied_to_next=last_note.tied_to_next)
        )
        length = total - first
    state.pending_broken = None
    return length


def _read_note(body: str, position: int, state: _BodyState) -> int | None:
    """Read a note or rest.

    Returns:
        The position after it, or None if there is no note here.
    """
    note_match = NOTE_PATTERN.match(body, position)
    if not note_match:
        return None
    accidental, letter, octave_marks, length_text, tie = note_match.groups()
    position = note_match.end()
    length = state.unit * parse_fraction(length_text)
    if state.triplet_left:
        length *= state.triplet_scale
        state.triplet_left -= 1
    if state.pending_broken and state.tokens:
        length = _apply_broken_rhythm(state, length)
    if letter == 'z':
        state.tokens.append(NoteToken(note=Note(midi=None, whole_notes=length)))
        return position
    upper = letter.upper()
    octave = 4 if letter.isupper() else 5
    octave += octave_marks.count("'") - octave_marks.count(',')
    if accidental is not None:
        state.bar_accidentals[upper, octave] = ACCIDENTAL_SHIFTS[accidental]
    shift = state.bar_accidentals.get((upper, octave), state.signature[upper])
    midi = 12 * (octave + 1) + LETTER_SEMITONES[upper] + shift
    state.tokens.append(
        NoteToken(note=Note(midi=midi, whole_notes=length, tied_to_next=tie == '-'))
    )
    return position


def parse_body(body: str, *, unit: Fraction, signature: dict[str, int]) -> list[Token]:
    """Read a tune's body into tokens.

    Args:
        body: The tune's music lines joined by spaces.
        unit: The default note length (the L: header), in whole notes.
        signature: The key signature's accidental for each letter.

    Returns:
        Its tokens: notes and rests, bar lines and ending brackets.
    """
    body = _strip_annotations(body)
    state = _BodyState(unit=unit, signature=signature)
    position = 0
    while position < len(body):
        # the first reader that recognises the text at this position wins; unknown text is skipped
        for reader in (_read_bar, _read_ending, _read_triplet, _read_broken_rhythm, _read_note):
            next_position = reader(body, position, state)
            if next_position is not None:
                break
        else:
            next_position = position + 1
        position = next_position
    return state.tokens


def _starts_repeat(token: Token) -> bool:
    """Whether the token is a ``|:`` style bar line that opens a repeated section.

    Returns:
        True for such a bar line.
    """
    return (
        isinstance(token, BarToken)
        and token.text.startswith('|')
        and token.text.endswith(':')
        and ':' not in token.text[:-1]
    )


def _ends_repeat(token: Token) -> TypeGuard[BarToken]:
    """Whether the token is a ``:|`` style bar line that closes a repeated section.

    Returns:
        True for such a bar line.
    """
    return isinstance(token, BarToken) and token.text.startswith(':')


def _is_second_ending(token: Token) -> bool:
    """Whether the token is the ``[2`` ending bracket.

    Returns:
        True for it.
    """
    return isinstance(token, EndingToken) and token.number == SECOND_ENDING


def _split_sections(tokens: list[Token]) -> list[tuple[list[Token], bool]]:
    """Cut the tokens into (tokens, repeated) sections at repeat bar lines.

    Returns:
        The sections, each with whether it is repeated.
    """
    sections: list[tuple[list[Token], bool]] = []
    current: list[Token] = []
    for token in tokens:
        if _starts_repeat(token):
            if current:
                sections.append((current, False))
            current = [token]
            continue
        current.append(token)
        if _ends_repeat(token):
            # the end of a repeated section (::, :|, :|:); a :|: also starts the next
            sections.append((current, True))
            current = []
            if token.text.endswith(':') and len(token.text) > 1:
                current = [BarToken(text='|:')]
    if current:
        sections.append((current, False))
    return sections


def _play_sections(sections: list[tuple[list[Token], bool]]) -> list[Token]:
    """Lay the sections out in playing order: repeated ones twice, with their endings chosen.

    Returns:
        The tokens in playing order.
    """
    played: list[Token] = []
    for index in range(len(sections)):
        section, repeated = sections[index]
        if not repeated:
            # a section after a repeat may begin with its [2 ending: those bars belong to the
            # repeat's second pass
            played.extend(section)
            continue
        first_pass = _without_ending(section, keep=1)
        second_pass = _without_ending(section, keep=SECOND_ENDING)
        played.extend(first_pass)
        follow = sections[index + 1][0] if index + 1 < len(sections) else []
        if any(_is_second_ending(token) for token in follow[:3]):
            played.extend(_without_ending(section, keep=0))
            played.extend(_take_ending_two(follow))
            sections[index + 1] = (_drop_ending_two(follow), sections[index + 1][1])
        else:
            played.extend(second_pass)
    return played


def expand_repeats(tokens: list[Token]) -> list[list[Note]]:
    """Bars in playing order: |: ... :| twice, with [1 played the first time and [2 the second.

    Args:
        tokens: The tokens from ``parse_body``.

    Returns:
        The bars, each a list of the notes in it.
    """
    played = _play_sections(_split_sections(tokens))
    bars: list[list[Note]] = []
    bar: list[Note] = []
    for token in played:
        if isinstance(token, NoteToken):
            bar.append(token.note)
        elif isinstance(token, BarToken) and bar:
            bars.append(bar)
            bar = []
    if bar:
        bars.append(bar)
    return bars


def _without_ending(section: list[Token], *, keep: int) -> list[Token]:
    """Remove the endings other than ``keep`` (0 = drop all endings) from a section.

    Returns:
        The section's remaining tokens.
    """
    result: list[Token] = []
    in_ending: int | None = None
    for token in section:
        if isinstance(token, EndingToken):
            in_ending = token.number
            continue
        if in_ending is not None and in_ending != keep:
            if isinstance(token, BarToken):
                # an ending lasts to the next bar line that closes it (one bar, the usual case)
                in_ending = None
            continue
        if isinstance(token, BarToken) and in_ending is not None:
            in_ending = None
        result.append(token)
    return result


def _take_ending_two(section: list[Token]) -> list[Token]:
    """Take the section's ``[2`` ending, up to and including its closing bar line.

    Returns:
        The tokens of that ending.
    """
    result: list[Token] = []
    started = False
    for token in section:
        if _is_second_ending(token):
            started = True
            continue
        if started:
            result.append(token)
            if isinstance(token, BarToken):
                break
    return result


def _drop_ending_two(section: list[Token]) -> list[Token]:
    """Remove the section's ``[2`` ending.

    Returns:
        The section's remaining tokens.
    """
    result: list[Token] = []
    skipping = False
    for token in section:
        if _is_second_ending(token):
            skipping = True
            continue
        if skipping:
            if isinstance(token, BarToken):
                skipping = False
            continue
        result.append(token)
    return result


def read_tune(text: str) -> Tune:
    """Read an ABC tune.

    Args:
        text: The contents of an ``.abc`` file.

    Returns:
        The tune, its bars in playing order.
    """
    headers: dict[str, str] = {}
    body_lines: list[str] = []
    for line in text.splitlines():
        header = re.match(r'^([A-Za-z]):\s*(.*)$', line)
        if header and not body_lines:
            headers[header.group(1)] = header.group(2).strip()
        elif line.strip():
            body_lines.append(line)
    meter_text = headers.get('M', '4/4').replace('C|', '2/2').replace('C', '4/4')
    numerator, _, denominator = meter_text.partition('/')
    meter = Fraction(int(numerator), int(denominator))
    compound = (
        int(denominator) == EIGHTH_NOTE_DENOMINATOR
        and int(numerator) % EIGHTHS_PER_COMPOUND_BEAT == 0
        and int(numerator) > EIGHTHS_PER_COMPOUND_BEAT
    )
    beats_per_bar = int(numerator) // EIGHTHS_PER_COMPOUND_BEAT if compound else int(numerator)
    unit = (
        parse_fraction('1/' + headers['L'].split('/')[1])
        if 'L' in headers
        else (Fraction(1, 16) if meter < Fraction(3, 4) else Fraction(1, 8))
    )
    signature, relative_major = key_signature(headers.get('K', 'C'))
    tokens = parse_body(' '.join(body_lines), unit=unit, signature=signature)
    return Tune(
        title=headers.get('T', 'untitled'),
        meter=meter,
        beats_per_bar=beats_per_bar,
        compound=compound,
        relative_major_pitch_class=relative_major,
        key_signature=signature,
        bars=expand_repeats(tokens),
    )


# --- Arranging --------------------------------------------------------------------------------

# Written Highland pitches (ABC G to a) at the chanter's real frequencies
HIGHLAND_WRITTEN = {
    67: 'LG',
    69: 'LA',
    71: 'B',
    73: 'C',
    74: 'D',
    76: 'E',
    78: 'F',
    79: 'HG',
    81: 'HA',
}
UILLEANN_LOW_MIDI, UILLEANN_HIGH_MIDI = 62, 88  # D4 to E6, the chanter's two octaves
UILLEANN_CUT_MIDI = 81  # high A: a cut is a flick of it before a long note below it
UILLEANN_CUT_MINIMUM_SECONDS = 0.3  # a bar-opening note this long gets a cut
UILLEANN_CUT_SECONDS = 0.025
UILLEANN_REPEAT_MINIMUM_SECONDS = 0.08  # a repeated note this long gets a breath before it
UILLEANN_BREATH_SECONDS = 0.035  # the chanter closes this long between repeated notes
UILLEANN_CHORDS = {  # regulator chords for each relative major
    2: {
        'D': (146.83, 185.00, 220.00),
        'G': (196.00, 246.94, 293.66),
        'A': (220.00, 277.18, 329.63),
    },
    7: {
        'G': (196.00, 246.94, 293.66),
        'C': (130.81, 164.81, 196.00),
        'D': (146.83, 185.00, 220.00),
    },
}
CHORD_FOR_PITCH_CLASS = {
    2: {2: 'D', 6: 'D', 9: 'D', 7: 'G', 11: 'G', 4: 'A', 1: 'A'},
    7: {7: 'G', 11: 'G', 2: 'G', 0: 'C', 4: 'C', 9: 'D', 6: 'D'},
}


def midi_to_hz(midi: float) -> float:
    """Convert a MIDI note number to its equal-tempered frequency (A4 = 440 Hz).

    Args:
        midi: The MIDI note number.

    Returns:
        The frequency in hertz.
    """
    return 440.0 * 2 ** ((midi - 69) / 12)


def uilleann_transposition(tune: Tune) -> int:
    """Semitones that move the tune to relative major D or G (whichever is nearer) and into range.

    Args:
        tune: The tune to place.

    Returns:
        The transposition in semitones.
    """
    pitches = [note.midi for bar in tune.bars for note in bar if note.midi is not None]

    def score(total: int) -> tuple[int, int]:
        """Score a move: notes outside the chanter's range, then its size (smaller is better).

        Returns:
            The score.
        """
        outside = sum(
            1 for pitch in pitches if not UILLEANN_LOW_MIDI <= pitch + total <= UILLEANN_HIGH_MIDI
        )
        return outside, abs(total)

    candidates = [
        candidate + octave_shift
        for target in (2, 7)
        for octave_shift in (-24, -12, 0, 12, 24)
        for shift in ((target - tune.relative_major_pitch_class) % 12,)
        for candidate in (shift, shift - 12)
    ]
    # min keeps the first of equal scores, as the search it replaces did
    return min(candidates, key=score)


def chanter_events(
    tune: Tune, *, seconds_per_whole: float, instrument: str, transposition: int
) -> list[tuple[float | str, float]]:
    """Notes for the chanter: ties joined; graces (Highland) or cuts and breaths (uilleann).

    Args:
        tune: The tune to play.
        seconds_per_whole: How long a whole note lasts.
        instrument: ``'highland'`` or ``'uilleann'``.
        transposition: Semitones to move every note by.

    Returns:
        (frequency or ``'_'`` for silence, seconds) pairs.
    """
    events: list[tuple[float | str, float]] = []
    previous: int | None = None
    tied = False
    for bar in tune.bars:
        for index, note in enumerate(bar):
            seconds = float(note.whole_notes) * seconds_per_whole
            if note.midi is None:
                events.append(('_', seconds))
                previous, tied = None, False
                continue
            midi = note.midi + transposition
            if tied and midi == previous:
                pitch, held = events[-1]
                events[-1] = (pitch, held + seconds)
                tied = note.tied_to_next
                continue
            if instrument == 'highland':
                frequency = highland_frequency(midi)
                if midi == previous and seconds > HIGHLAND_GRACE_SECONDS * 2:
                    events.append((HIGHLAND_SCALE['HG'], HIGHLAND_GRACE_SECONDS))
                    seconds -= HIGHLAND_GRACE_SECONDS
            else:
                frequency = midi_to_hz(midi)
                if (
                    index == 0
                    and seconds >= UILLEANN_CUT_MINIMUM_SECONDS
                    and midi < UILLEANN_CUT_MIDI
                ):
                    # a cut: a flick of high A
                    events.append((midi_to_hz(UILLEANN_CUT_MIDI), UILLEANN_CUT_SECONDS))
                    seconds -= UILLEANN_CUT_SECONDS
                if midi == previous and seconds > UILLEANN_REPEAT_MINIMUM_SECONDS:
                    events.append((
                        '_',
                        UILLEANN_BREATH_SECONDS,
                    ))  # close the chanter between repeats
                    seconds -= UILLEANN_BREATH_SECONDS
            events.append((frequency, seconds))
            previous = midi
            tied = note.tied_to_next
    return events


def highland_frequency(midi: int) -> float:
    """A written Highland note's sounding frequency.

    The chanter's own scale is used where it has the note.

    Args:
        midi: The written note's MIDI number.

    Returns:
        The frequency in hertz.
    """
    if midi in HIGHLAND_WRITTEN:
        return HIGHLAND_SCALE[HIGHLAND_WRITTEN[midi]]
    return HIGHLAND_SCALE['LA'] * 2 ** ((midi - 69) / 12)


def regulator_layers(
    tune: Tune, *, seconds_per_whole: float, transposition: int, start_frame: int
) -> list[tuple[npt.NDArray[np.float64], int, float]]:
    """The regulator stabs as mix layers: one chord per full bar, on the beats after the first.

    Args:
        tune: The tune being arranged.
        seconds_per_whole: How long a whole note lasts.
        transposition: Semitones the chanter was moved by.
        start_frame: The frame where the chanter enters.

    Returns:
        (samples, start frame, gain) mix layers; none when no regulator chords fit the key.
    """
    relative_major = (tune.relative_major_pitch_class + transposition) % 12
    chords = UILLEANN_CHORDS.get(relative_major)
    if chords is None:
        return []
    stabs = {
        name: render(
            uilleann_regulators,
            name=f'tune_regulator_{name}',
            chord=[Hz(frequency) for frequency in frequencies],
            length=UILLEANN_REGULATOR_STAB_SECONDS,
        )
        for name, frequencies in chords.items()
    }
    beats_per_bar = tune.beats_per_bar
    beat_seconds = float(tune.meter) * seconds_per_whole / beats_per_bar
    layers: list[tuple[npt.NDArray[np.float64], int, float]] = []
    elapsed = 0.0
    for bar in tune.bars:
        # (length, MIDI number) of each note with a pitch; max keeps the first longest
        sounding = [(note.whole_notes, note.midi) for note in bar if note.midi is not None]
        bar_seconds = sum(float(note.whole_notes) for note in bar) * seconds_per_whole
        if sounding and math.isclose(
            bar_seconds, float(tune.meter) * seconds_per_whole, rel_tol=0.05
        ):
            _length, longest_midi = max(sounding, key=operator.itemgetter(0))
            chord = CHORD_FOR_PITCH_CLASS[relative_major].get(
                (longest_midi + transposition) % 12, next(iter(chords))
            )
            layers.extend(
                (
                    stabs[chord],
                    start_frame + round((elapsed + beat * beat_seconds) * SAMPLE_RATE),
                    0.3,
                )
                for beat in range(1, beats_per_bar)
            )
        elapsed += bar_seconds
    return layers


def arrange(
    tune: Tune, *, instrument: str, quarter_bpm: float, name: str
) -> npt.NDArray[np.float64]:
    """Render the tune with its drones (and, on the uilleann pipes, regulator chords).

    Args:
        tune: The tune to play.
        instrument: ``'highland'`` or ``'uilleann'``.
        quarter_bpm: The tempo (dotted quarters a minute for a jig, else quarter notes).
        name: The base name of the rendered sounds.

    Returns:
        The mixed mono samples.
    """
    # A jig's tempo is counted in dotted quarters (its beat); every other meter's in quarter notes
    beat_whole_notes = 3 / 8 if tune.compound else 1 / 4
    seconds_per_whole = 60.0 / quarter_bpm / beat_whole_notes
    chanter_start = SAMPLE_RATE
    if instrument == 'highland':
        chanter = render(
            highland_chanter,
            name=f'{name}_chanter',
            notes=chanter_events(
                tune, seconds_per_whole=seconds_per_whole, instrument='highland', transposition=0
            ),
        )
        drones = render(
            highland_drones,
            name=f'{name}_drones',
            pitch=Hz(HIGHLAND_TENOR_DRONE_HZ),
            length=1.0 + len(chanter) / SAMPLE_RATE + 0.5,
        )
        return mix((drones, 0, 0.55), (chanter, chanter_start, 1.0))
    transposition = uilleann_transposition(tune)
    chanter = render(
        uilleann_chanter,
        name=f'{name}_chanter',
        notes=chanter_events(
            tune,
            seconds_per_whole=seconds_per_whole,
            instrument='uilleann',
            transposition=transposition,
        ),
    )
    drones = render(
        uilleann_drones,
        name=f'{name}_drones',
        pitch=Hz(146.83),
        length=1.0 + len(chanter) / SAMPLE_RATE + 1.0,
    )
    regulators = regulator_layers(
        tune,
        seconds_per_whole=seconds_per_whole,
        transposition=transposition,
        start_frame=chanter_start,
    )
    return mix((drones, 0, 0.35), (chanter, chanter_start, 0.8), *regulators) * (10 ** (-8 / 20))


def tune_samples(entry: Mapping[str, str | float]) -> npt.NDArray[np.float64]:
    """Render one tune of the index (``index.json``) on its instrument.

    A tune marked for the Highland pipes with a note outside the Highland chanter's nine goes on
    the uilleann pipes, which can play it.

    Args:
        entry: The tune's entry in ``index.json``.

    Returns:
        Its samples.
    """
    tune = read_tune((TUNES_DIRECTORY / str(entry['file'])).read_text(encoding='utf-8'))
    instrument = entry.get('suggested_instrument', 'uilleann')
    if instrument == 'highland' and any(
        note.midi is not None and note.midi not in HIGHLAND_WRITTEN
        for bar in tune.bars
        for note in bar
    ):
        instrument = 'uilleann'
    return arrange(
        tune,
        instrument=str(instrument),
        quarter_bpm=float(entry.get('suggested_tempo_quarter_bpm', 100)),
        name=Path(str(entry['file'])).stem,
    )


def tune_entries() -> list[dict[str, str | float]]:
    """Return the tunes' index (``tunes/index.json``: title, file, instrument, tempo per tune).

    Returns:
        Its entries, in order.
    """
    entries: list[dict[str, str | float]] = json.loads(
        (TUNES_DIRECTORY / TUNES_INDEX_FILE).read_text(encoding='utf-8')
    )
    return entries


def tune_name(entry: Mapping[str, str | float]) -> str:
    """Return a tune's file name without its suffix (its WAV file's name).

    Returns:
        The name.
    """
    return Path(str(entry['file'])).stem
