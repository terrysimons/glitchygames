"""The saves door: games open their save store through the active sources.

Live play gets a real ``SaveManager``. A recording stores each opened store's slots (their full
envelopes) when recording starts or when the store is opened later, and a replay or in-game
playback gets a ``SandboxSaves`` seeded from them: reads see what the original session saw, and
writes stay in memory and are discarded, so a replay never touches real saves.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Self

from glitchygames.sources import active_sources
from glitchygames.state.exceptions import SaveNotFoundError

if TYPE_CHECKING:
    from glitchygames.state.manager import SaveManager
    from glitchygames.state.save_store import SaveStore

# The envelope key holding the game's data (glitchygames/state/manager.py _DATA_KEY)
DATA_KEY = 'data'


class SandboxSaves:
    """An in-memory save store seeded from recorded envelopes; writes are discarded at exit.

    Implements glitchygames.state.save_store.SaveStore with ``SaveManager``'s positional
    signatures (a drop-in: interface conformance).
    """

    def __init__(self: Self, *, app_name: str, envelopes: dict[str, dict[str, Any]]) -> None:
        """Copy the recorded envelopes (the recording is never modified).

        Args:
            app_name: The application name (the save namespace) this store stands in for.
            envelopes: Slot name -> full save envelope, as save_namespace_snapshot returns.

        """
        self._app_name = app_name
        self._envelopes = copy.deepcopy(envelopes)

    @property
    def app_name(self: Self) -> str:
        """The application name this store is scoped to."""
        return self._app_name

    def load(self: Self, slot_name: str) -> dict[str, Any]:
        """Return a slot's data.

        Positional like ``SaveManager.load`` (a drop-in: interface conformance).

        Args:
            slot_name: Name of the save slot to load.

        Returns:
            A copy of the slot's data.

        Raises:
            SaveNotFoundError: If the slot does not exist, as SaveManager does.

        """
        envelope = self._envelopes.get(slot_name)
        if envelope is None:
            message = f"No save slot '{slot_name}' in the replay's save snapshot"
            raise SaveNotFoundError(message=message, slot_name=slot_name)
        return copy.deepcopy(envelope[DATA_KEY])

    def save(self: Self, slot_name: str, data: dict[str, Any]) -> None:
        """Keep the data in memory only.

        Positional like ``SaveManager.save`` (a drop-in: interface conformance).

        Args:
            slot_name: Name of the save slot.
            data: Game state to keep.

        """
        self._envelopes[slot_name] = {DATA_KEY: copy.deepcopy(data)}

    def exists(self: Self, slot_name: str) -> bool:
        """Return whether the slot exists in the sandbox.

        Positional like ``SaveManager.exists`` (a drop-in: interface conformance).

        Args:
            slot_name: Name of the save slot to check.

        Returns:
            True if the sandbox holds the slot.

        """
        return slot_name in self._envelopes

    def delete(self: Self, slot_name: str) -> None:
        """Remove the slot from the sandbox.

        Positional like ``SaveManager.delete`` (a drop-in: interface conformance).

        Args:
            slot_name: Name of the save slot to delete.

        Raises:
            SaveNotFoundError: If the slot does not exist, as SaveManager does.

        """
        if slot_name not in self._envelopes:
            message = f"No save slot '{slot_name}' in the replay's save snapshot"
            raise SaveNotFoundError(message=message, slot_name=slot_name)
        del self._envelopes[slot_name]

    def envelopes(self: Self) -> dict[str, dict[str, Any]]:
        """Return a deep copy of every slot's envelope.

        A recording made over a replay snapshots a sandbox (--rebaseline), and so does a scene
        start inside one.

        Returns:
            Slot name -> envelope.

        """
        return copy.deepcopy(self._envelopes)


def save_namespace_snapshot(*, saves: SaveManager | SandboxSaves) -> dict[str, dict[str, Any]]:
    """Return every slot of a store as its full envelope (slot name -> envelope).

    Args:
        saves: A real store, or the sandbox a replay hands out.

    Returns:
        The JSON-safe snapshot a recording stores.

    """
    if isinstance(saves, SandboxSaves):
        return saves.envelopes()
    return {slot.name: saves.load_raw(slot_name=slot.name) for slot in saves.list_slots()}


def open_saves(*, app_name: str) -> SaveStore:
    """Open a game's save store through the active sources (glitchygames/sources.py).

    Args:
        app_name: The application name (the save namespace).

    Returns:
        The store: a SaveManager live, a SandboxSaves in a replay.

    """
    return active_sources().saves(namespace=app_name)
