"""The catalog's entry type, families and tags (the tables are in the family modules).

A ``CatalogEntry`` names an instrument, its family and its playing range (sounding pitch, from
standard orchestration ranges; folk and world instruments vary by maker and tuning, so theirs
are typical). Unpitched entries (drums, cymbals) have no range: their tones are fixed. A ``Tag``
marks a quality that cuts across families (``Tag.MECHANICAL``, ``Tag.CHIP``); the set is closed,
so tags cannot drift into synonyms. A sound-alike (``sounds_like``) is an instrument of its own
that no source sets apart in sound from another entry, its parent: it is listed under its own name
and builds its parent's instrument, changed only by its sourced ``sound_changes``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from glitchygames.audio.pitch import Note

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

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
    ELECTROMECHANICAL = 'electromechanical'
    ELECTRONIC = 'electronic'
    TUNED_PERCUSSION = 'tuned percussion'
    PLUCKED_IDIOPHONES = 'plucked idiophones'
    FRICTION_INSTRUMENTS = 'friction instruments'
    DRUMS_AND_PERCUSSION = 'drums and percussion'
    NOISE_MAKERS = 'noise makers'
    SOUND_EFFECTS = 'sound effects'
    VOICES = 'voices'
    CHOIRS = 'choirs'


class Tag(StrEnum):
    """The closed set of tags an entry may carry, across families."""

    MECHANICAL = 'mechanical'
    # A voice of a sound chip. https://en.wikipedia.org/wiki/Sound_chip: "A sound chip is an
    # integrated circuit (chip) designed to produce audio signals through digital, analog or
    # mixed-mode electronics."
    CHIP = 'chip'


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One catalog instrument.

    Attributes:
        name: Its catalog name (``alto saxophone``): lower-case words separated by single spaces.
        title: Its display name (``Alto saxophone``).
        family: Its family.
        lowest: Its lowest sounding note name, or None when it is unpitched.
        highest: Its highest sounding note name, or None when it is unpitched.
        build: Makes the instrument (called once; ``instruments.get`` keeps the result). Every
            entry from ``CATALOG`` / ``instruments.entry()`` has a build: None only in a raw
            table entry for a sound-alike, which the catalog's assembly gives its parent's
            builder.
        tags: Its tags, members of ``Tag`` (empty for most entries).
        sounds_like: The catalog name of the entry this one sounds like (its parent), or None.
            A sound-alike is a distinct instrument, listed under its own name, that no source
            sets apart in sound from its parent: it builds its parent's instrument. It is pitched
            exactly when its parent is, and a pitched one gives its own sourced range (decision 8,
            plans/2026-11-07-instrument-catalog-expansion-design.md, and
            plans/2026-11-09-instrument-catalog-batch-4-implementation.md); another name for the
            same instrument is an alias instead.
        sound_changes: Keyword overrides of the parent's builder (a ``functools.partial``), for
            a sound-alike that a source sets apart by a trait (a smaller head's higher tone)
            while it inherits everything else; empty for most. Each change needs a source,
            cited in the entry's comment, as every other value does. Stored read-only.
    """

    name: str
    title: str
    family: Family
    lowest: str | None
    highest: str | None
    build: Callable[[], Instrument] | None = field(default=None, repr=False, compare=False)
    tags: frozenset[Tag] = field(default=frozenset())
    sounds_like: str | None = None
    # compare=False: a mappingproxy is unhashable and the frozen entry must stay hashable, so
    # equality ignores the changes
    sound_changes: Mapping[str, object] = field(default=MappingProxyType({}), compare=False)

    def __post_init__(self) -> None:
        """Validate the name, the range, the tags and the build, and freeze the sound changes.

        The sound-alike rules that need the whole catalog (the parent exists, is no sound-alike,
        takes the changes) are checked when the catalog is assembled
        (``registry.sound_alikes_from``).

        Raises:
            ValueError: On a name that is not lower-case words separated by single spaces, a range
                with only one end, a note name that does not parse, a lowest note above the
                highest, or neither a build nor a ``sounds_like``.
            TypeError: On a tag that is not a ``Tag`` (a string equal to a tag's value included).
        """
        # A copy, so the caller's dict cannot change the entry afterwards
        object.__setattr__(self, 'sound_changes', MappingProxyType(dict(self.sound_changes)))
        if self.build is None and self.sounds_like is None:
            message = f'{self.name}: give a build, or the entry it sounds like'
            raise ValueError(message)
        if ENTRY_NAME_PATTERN.fullmatch(self.name) is None:
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
        for tag in self.tags:
            if type(tag) is not Tag:
                message = f'{self.name}: tag {tag!r} must be a Tag'
                raise TypeError(message)

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
