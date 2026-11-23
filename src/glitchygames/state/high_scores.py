"""A game's high-score table, kept in one save slot.

PaddleSlap, Brave Adventurer, Clockwork Keep and Mr. Muncher each kept their own copy of this
(plans/2026-11-20-game-code-into-the-engine.md, sub-plan 2). The table makes exactly the save
calls those copies made, because every replay records the save door's calls:

- ``record()``: one ``load``, then one ``save`` of ``{'scores': [...]}``;
- ``entries()`` and ``best()``: one ``load`` each, and no save.

The slot holds ``{'scores': [entry, ...]}``, best first, each entry a dictionary in its model's
field order (``{'score': 900, 'floor': 3}``), the shape players' save files already have. Entries
are strict pydantic models: a game that saves more than the score subclasses ``HighScoreEntry``.
An entry that fails validation is refused (``SaveCorruptedError``, the file left as it is) or
dropped with a warning, as ``HighScoreTableSettings.invalid_entries`` says; games take it from
``--invalid-high-scores``. One player per table for now: player names wait for the roster
(plans/2026-10-28-player-roster-design.md).
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Self

import pydantic

from glitchygames.state.exceptions import SaveCorruptedError, SaveNotFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glitchygames.state.manager import SaveManager

LOG = logging.getLogger(__name__)

# The command-line option that picks the policy for invalid entries (GameEventManager.args)
INVALID_HIGH_SCORES_OPTION = 'invalid_high_scores'


class BestScore(StrEnum):
    """Which end of the table is best."""

    # The highest score first (points)
    HIGHEST = 'highest'
    # The lowest score first (a time trial's time)
    LOWEST = 'lowest'


class InvalidEntries(StrEnum):
    """What the table does with a saved entry that fails validation."""

    # Raise SaveCorruptedError and save nothing, so the file stays exactly as found
    REFUSE = 'refuse'
    # Leave it out with a warning; the next save writes the table without it
    DROP = 'drop'


class HighScoreEntry(pydantic.BaseModel):
    """One high score: the score alone. Games that save more subclass it, adding fields."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid', strict=True)

    score: int


class HighScoreTableSettings(pydantic.BaseModel):
    """Where a table is kept, how long it is, which end is best, and the invalid-entry policy."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    slot_name: str = 'high_scores'
    limit: int = 10
    best: BestScore = BestScore.HIGHEST
    invalid_entries: InvalidEntries = InvalidEntries.REFUSE

    @classmethod
    def from_options(cls, *, options: Mapping[str, Any], **settings: Any) -> Self:
        """Return settings whose invalid-entry policy is the game's ``--invalid-high-scores``.

        Args:
            options: The game's options (an option left out keeps the default policy).
            **settings: Any other settings.

        Returns:
            The settings.

        """
        policy = options.get(INVALID_HIGH_SCORES_OPTION, InvalidEntries.REFUSE)
        return cls(invalid_entries=InvalidEntries(policy), **settings)


class HighScoreTable[EntryT: HighScoreEntry]:
    """A game's best scores, in one save slot (a plain class: it holds a SaveManager)."""

    def __init__(
        self: Self,
        *,
        saves: SaveManager,
        entry_type: type[EntryT],
        settings: HighScoreTableSettings | None = None,
    ) -> None:
        """Keep the store, the game's entry model and the settings.

        Args:
            saves: The game's save store.
            entry_type: The game's entry model (``HighScoreEntry`` or a subclass of it).
            settings: The table's settings (None: the defaults).

        """
        self.saves = saves
        self.entry_type = entry_type
        self.settings = HighScoreTableSettings() if settings is None else settings

    def entries(self: Self) -> list[EntryT]:
        """Return the saved table, in the file's order (best first, as it was saved).

        Returns:
            The entries (empty when there is no table).

        """
        return self._load()

    def best(self: Self) -> int:
        """Return the best saved score.

        Returns:
            The first entry's score, or 0 when there is no table.

        """
        entries = self._load()
        return entries[0].score if entries else 0

    def record(self: Self, entry: EntryT) -> list[EntryT]:
        """Add a score, keep the best ``limit`` of them, and save the table.

        The sort is stable, so a new score equal to a saved one goes below it, and a full
        table whose lowest equals the new score keeps the saved one.

        Args:
            entry: The new score.

        Returns:
            The saved table, best first.

        """
        entries: list[EntryT] = [*self._load(), entry]
        entries.sort(key=_score, reverse=self.settings.best is BestScore.HIGHEST)
        kept = entries[: self.settings.limit]
        self.saves.save(
            self.settings.slot_name, {'scores': [kept_entry.model_dump() for kept_entry in kept]}
        )
        return kept

    def _load(self: Self) -> list[EntryT]:
        """Load and validate the saved entries (one load).

        Returns:
            The valid entries, in the file's order.

        Raises:
            SaveCorruptedError: An entry is invalid and the policy refuses it.

        """
        slot_name = self.settings.slot_name
        try:
            saved = self.saves.load(slot_name)
        except SaveNotFoundError:
            return []
        entries: list[EntryT] = []
        for data in saved.get('scores', []):
            try:
                entries.append(self.entry_type.model_validate(data))
            except pydantic.ValidationError as error:
                if self.settings.invalid_entries is InvalidEntries.REFUSE:
                    message = f'The {slot_name} save holds an invalid high score: {data!r}'
                    raise SaveCorruptedError(
                        message=message,
                        path=self.saves.find_slot_path(slot_name),
                        original_error=error,
                    ) from error
                LOG.warning('Dropping an invalid high score from %s: %r', slot_name, data)
        return entries

    # What a game's game-over flow calls: a table the policy refuses never costs the player the
    # score they just made, and never stops the game. Each makes the same save calls as the
    # method it wraps.

    def record_or_keep(self: Self, entry: EntryT) -> list[EntryT]:
        """Record a score; when the saved table is refused, log it and keep the file as it is.

        Args:
            entry: The new score.

        Returns:
            The saved table, best first, or a table of the new score alone when refused.

        """
        try:
            return self.record(entry)
        except SaveCorruptedError as refusal:
            error = refusal
        LOG.error('High score not saved, the saved table was left as it is: %s', error)
        return [entry]

    def entries_or(self: Self, fallback: list[EntryT]) -> list[EntryT]:
        """Return the saved table, or a fallback when it is refused (already logged by a save).

        Args:
            fallback: What to show instead (the run's own entry).

        Returns:
            The entries, or the fallback.

        """
        try:
            return self.entries()
        except SaveCorruptedError:
            LOG.debug('The saved table is refused; showing %r instead', fallback)
            return fallback

    def best_or_zero(self: Self) -> int:
        """Return the best saved score; when the saved table is refused, log it and return 0.

        Returns:
            The best score, or 0.

        """
        try:
            return self.best()
        except SaveCorruptedError as refusal:
            error = refusal
        LOG.error('The saved high scores are refused, the best is 0 for now: %s', error)
        return 0


def _score(entry: HighScoreEntry) -> int:
    """Return an entry's score (the table's sort key).

    Returns:
        The score.

    """
    return entry.score
