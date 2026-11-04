"""The catalog's entry type and families (the tables are in the family modules).

A ``CatalogEntry`` names an instrument, its family and its playing range (sounding pitch, from
standard orchestration ranges; folk and world instruments vary by maker and tuning, so theirs
are typical). Unpitched entries (drums, cymbals) have no range: their tones are fixed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from glitchygames.audio.pitch import Note

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.audio.instrument import Instrument

ENTRY_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r'^[a-z][a-z0-9]*( [a-z0-9]+)*$')


class Family(StrEnum):
    """The instrument families, in the order the catalog lists them."""

    FLUTES = 'flutes'
    CLARINETS = 'clarinets'
    SAXOPHONES = 'saxophones'
    DOUBLE_REEDS = 'double reeds'
    BAGPIPES = 'bagpipes'
    FREE_REEDS = 'free reeds'
    BRASS = 'brass'
    BOWED_STRINGS = 'bowed strings'
    PLUCKED_STRINGS = 'plucked strings'
    HARPS = 'harps'
    STRUCK_STRINGS = 'struck strings'
    KEYBOARDS = 'keyboards'
    ORGANS = 'organs'
    ELECTRONIC = 'electronic'
    TUNED_PERCUSSION = 'tuned percussion'
    DRUMS_AND_PERCUSSION = 'drums and percussion'
    VOICES = 'voices'
    CHOIRS = 'choirs'


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One catalog instrument.

    Attributes:
        name: Its catalog name (``alto saxophone``): lower-case words separated by single spaces.
        title: Its display name (``Alto saxophone``).
        family: Its family.
        lowest: Its lowest sounding note name, or None when it is unpitched.
        highest: Its highest sounding note name, or None when it is unpitched.
        build: Makes the instrument (called once; ``instruments.get`` keeps the result).
    """

    name: str
    title: str
    family: Family
    lowest: str | None
    highest: str | None
    build: Callable[[], Instrument] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        """Validate the name and the range.

        Raises:
            ValueError: On a name that is not lower-case words separated by single spaces, a range
                with only one end, a note name that does not parse, or a lowest note above the
                highest.
        """
        if ENTRY_NAME_PATTERN.match(self.name) is None:
            message = (
                f'catalog name {self.name!r} must be lower-case words separated by single spaces'
            )
            raise ValueError(message)
        if (self.lowest is None) != (self.highest is None):
            message = f'{self.name}: give both ends of the range, or neither (unpitched)'
            raise ValueError(message)
        if (
            self.lowest is not None
            and self.highest is not None
            and Note(self.lowest).midi_number > Note(self.highest).midi_number
        ):
            message = f'{self.name}: lowest {self.lowest} is above highest {self.highest}'
            raise ValueError(message)

    @property
    def pitched(self) -> bool:
        """True when the instrument plays the note's pitch (it has a range)."""
        return self.lowest is not None

    @property
    def playing_range(self) -> tuple[Note, Note] | None:
        """The lowest and highest notes, or None when unpitched."""
        if self.lowest is None or self.highest is None:
            return None
        return Note(self.lowest), Note(self.highest)

    def middle_note(self) -> Note:
        """The note halfway through the range in semitones (A4 when unpitched).

        Returns:
            The note.
        """
        playing_range = self.playing_range
        if playing_range is None:
            return Note('A4')
        lowest, highest = playing_range
        return Note.from_midi_number((lowest.midi_number + highest.midi_number) // 2)
