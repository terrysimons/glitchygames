"""An in-memory save store that records every load and save (high-score tests share it).

The save door's calls are recorded in every replay, so the high-score table must make the same
calls, in the same order, as the games' own code did: tests compare these recordings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from glitchygames.state.sandbox import MemorySaveManager

if TYPE_CHECKING:
    from pathlib import Path

    from glitchygames.state.serializers import Serializer

SLOT = 'high_scores'


class RecordingSaves(MemorySaveManager):
    """An in-memory save store that records every load and save, in order."""

    def __init__(self) -> None:
        """Start empty, with no calls recorded."""
        super().__init__(app_name='high-score-test', snapshot={})
        self.calls: list[tuple[str, str, Any]] = []

    @override
    def load(self, slot_name: str, *, serializer: Serializer | None = None) -> dict[str, Any]:
        """Record the load, then load.

        Returns:
            The slot's data.

        """
        self.calls.append(('load', slot_name, None))
        return super().load(slot_name, serializer=serializer)

    @override
    def save(
        self, slot_name: str, data: dict[str, Any], *, serializer: Serializer | None = None
    ) -> Path:
        """Record the save, then save.

        Returns:
            Where the slot is kept.

        """
        self.calls.append(('save', slot_name, data))
        return super().save(slot_name, data, serializer=serializer)


def saves_holding(payload: dict[str, Any] | None) -> RecordingSaves:
    """Return a recording store whose high-score slot holds a payload (None: no slot).

    Returns:
        The store, with no calls recorded yet.

    """
    saves = RecordingSaves()
    if payload is not None:
        saves.save(SLOT, payload)
    saves.calls.clear()
    return saves
