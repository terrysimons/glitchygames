"""The SaveStore type: what games use of a save store.

This module is a leaf (it imports nothing from the package), so glitchygames/sources.py can name
the type under ``TYPE_CHECKING`` without an import cycle (glitchygames.state.manager comes to
import glitchygames.clock, which imports glitchygames.sources).
"""

from __future__ import annotations

from typing import Any, Protocol


class SaveStore(Protocol):
    """What games use of a save store (``SaveManager`` live, ``SandboxSaves`` in a replay).

    The methods keep ``SaveManager``'s positional signatures, so either is a drop-in for the
    other (interface conformance).
    """

    @property
    def app_name(self) -> str:
        """The application name this store is scoped to."""
        ...

    def load(self, slot_name: str) -> dict[str, Any]:
        """Return a slot's data."""
        ...

    def save(self, slot_name: str, data: dict[str, Any]) -> object:
        """Write a slot's data."""
        ...

    def exists(self, slot_name: str) -> bool:
        """Return whether the slot exists."""
        ...

    def delete(self, slot_name: str) -> None:
        """Remove the slot."""
        ...
