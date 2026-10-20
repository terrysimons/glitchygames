"""The supervisor hook and control events.

A supervisor is called once per frame at a fixed place in the frame (after logic and events,
before frame services, camera aim and positioning — see SceneManager._run_scene_frame), so what
it reads is the frame's final logic state and what it changes is drawn this frame and seen by
collision next frame. Today scripts/record_scripted_session.py uses it to play a golden input
script. The watched-replay controls and recorded breakpoints (Part 2) and a future cheat device
plug in here too (plans/2026-10-19-gameplay-replay.md, section 2).

A control event is a supervisor action recorded with the frame it happened in; a replay
re-applies recorded control events on the same frame, so sessions with supervisor actions replay
exactly.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, Self, cast

if TYPE_CHECKING:
    from glitchygames.scenes import Scene

BREAKPOINT_KIND = 'breakpoint'
PLAYBACK_KIND = 'playback'
KIND_FIELD = 'kind'
# Kinds a replay applies again on their frame (supervisor actions). Other kinds are markers
# the replayed code records again by itself (Part 3's playback scope); a replay compares them
# instead of applying them, so they are never doubled
REAPPLIED_CONTROL_EVENT_KINDS = frozenset({BREAKPOINT_KIND})


class Supervisor(Protocol):
    """Called once per frame at the supervisor slot."""

    def on_frame(self, *, frame_number: int, scene: Scene | None) -> None:
        """Inspect or act on frame ``frame_number``.

        Args:
            frame_number: The frame being run (SceneManager.frame_number).
            scene: SceneManager.active_scene at the slot. In a scene frame it is the scene
                whose logic and events just ran, or the scene they switched to (a switch
                during events, as resuming from the pause screen does, takes effect at once).
                In a transition frame it is the arriving scene: SceneManager._start_transition
                sets it up and makes it active before the effect plays, while the outgoing
                scene is already cleaned up. It is None only when no scene is active (before
                the first scene is installed, or after the last one ended).

        """
        ...


def _frozen(value: Any) -> Any:
    """Return a read-only copy of JSON-shaped ``value``: mappings and lists, recursively.

    Returns:
        A MappingProxyType over a copy for a mapping, a tuple for a list or tuple, else value.

    """
    if isinstance(value, Mapping):
        mapping = cast('Mapping[Any, Any]', value)
        return MappingProxyType({key: _frozen(item) for key, item in mapping.items()})
    if isinstance(value, list | tuple):
        return tuple(_frozen(item) for item in cast('list[Any] | tuple[Any, ...]', value))
    return value


def _thawed(value: Any) -> Any:
    """Return plain JSON types for a value made by ``_frozen`` (dicts and lists).

    Returns:
        A dict for a mapping, a list for a tuple or list, else value.

    """
    if isinstance(value, Mapping):
        mapping = cast('Mapping[Any, Any]', value)
        return {key: _thawed(item) for key, item in mapping.items()}
    if isinstance(value, list | tuple):
        return [_thawed(item) for item in cast('list[Any] | tuple[Any, ...]', value)]
    return value


@dataclasses.dataclass(frozen=True)
class ControlEvent:
    """A recorded supervisor action: its kind and JSON-safe data.

    ``data`` is a read-only copy of the mapping given (nested mappings become read-only
    mappings and lists become tuples), so nobody can change, after the fact, what the frame's
    handlers, ``end_frame`` and the recording see. ``to_json`` gives plain dicts and lists.
    """

    kind: str
    data: Mapping[str, Any]

    def __post_init__(self: Self) -> None:
        """Replace ``data`` with its read-only copy."""
        # The dataclass is frozen, so the field is set the way dataclasses set it
        object.__setattr__(self, 'data', _frozen(self.data))

    def to_json(self: Self) -> dict[str, Any]:
        """Return ``{'kind': kind, **data}`` as plain JSON types.

        Returns:
            The JSON-safe record.

        """
        return {KIND_FIELD: self.kind, **_thawed(self.data)}

    @classmethod
    def from_json(cls, record: Mapping[str, Any]) -> ControlEvent:
        """Read a record written by ``to_json``.

        Args:
            record: A record written by ``to_json``.

        Returns:
            The control event.

        """
        data = {name: value for name, value in record.items() if name != KIND_FIELD}
        return cls(kind=str(record[KIND_FIELD]), data=data)
