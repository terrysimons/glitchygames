"""The supervisor hook and control events.

A supervisor is called once per frame at a fixed place in the frame (after logic and events,
before frame services, camera aim and positioning — see SceneManager._run_scene_frame), so what
it reads is the frame's final logic state and what it changes is drawn this frame and seen by
collision next frame. The engine's scripted-session recorder (``--record-session``,
glitchygames/replay/tools/scripted_sessions.py) uses it to play an input script as a player's
input. The watched-replay controls and recorded breakpoints (Part 2) and a future cheat device
plug in here too (plans/2026-10-19-gameplay-replay.md, section 2).

Supervisors are the scene manager's, not a scene's: they run whichever scene is active, a
playback scope's included. One added while a playback scope plays belongs to the scope and is
removed when the scope ends (glitchygames/replay/playback.py, rule 4), so a rebuilt scene's
supervisor never outlives its playback; one added before the scope runs through it and stays.

A control event is a supervisor action recorded with the frame it happened in; a replay
re-applies recorded control events on the same frame, so sessions with supervisor actions replay
exactly.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, Self, cast, overload

if TYPE_CHECKING:
    from glitchygames.scenes import Scene
    from glitchygames.tracing import JsonValue

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


# A JSON value made read-only by frozen_json_value: mappings are read-only, lists are tuples
type FrozenJsonValue = (
    str | int | float | bool | tuple[FrozenJsonValue, ...] | Mapping[str, FrozenJsonValue] | None
)
# What frozen_json_value and thawed_json_value take: a plain or a frozen JSON value (the covariant
# Sequence and Mapping make both JsonValue and FrozenJsonValue members)
type JsonShapedValue = (
    str | int | float | bool | Sequence[JsonShapedValue] | Mapping[str, JsonShapedValue] | None
)


@overload  # pragma: no cover - a typing stub, never called (the implementation below is)
def frozen_json_value(value: Mapping[str, JsonShapedValue]) -> Mapping[str, FrozenJsonValue]: ...


@overload  # pragma: no cover - a typing stub, never called (the implementation below is)
def frozen_json_value(value: JsonShapedValue) -> FrozenJsonValue: ...


def frozen_json_value(value: object) -> object:
    """Return a read-only copy of JSON-shaped ``value``: mappings and lists, recursively.

    Used for control event data and ghost appearances (glitchygames/replay/ghosts.py).

    Returns:
        A MappingProxyType over a copy for a mapping, a tuple for a list or tuple, else value.

    """
    if isinstance(value, Mapping):
        mapping = cast('Mapping[str, JsonShapedValue]', value)
        return MappingProxyType({key: frozen_json_value(item) for key, item in mapping.items()})
    if isinstance(value, list | tuple):
        items = cast('list[JsonShapedValue] | tuple[JsonShapedValue, ...]', value)
        return tuple(frozen_json_value(item) for item in items)
    return value


@overload  # pragma: no cover - a typing stub, never called (the implementation below is)
def thawed_json_value(value: Mapping[str, JsonShapedValue]) -> dict[str, JsonValue]: ...


@overload  # pragma: no cover - a typing stub, never called (the implementation below is)
def thawed_json_value(value: JsonShapedValue) -> JsonValue: ...


def thawed_json_value(value: object) -> object:
    """Return plain JSON types for a value made by ``frozen_json_value`` (dicts and lists).

    Returns:
        A dict for a mapping, a list for a tuple or list, else value.

    """
    if isinstance(value, Mapping):
        mapping = cast('Mapping[str, JsonShapedValue]', value)
        return {key: thawed_json_value(item) for key, item in mapping.items()}
    if isinstance(value, list | tuple):
        items = cast('list[JsonShapedValue] | tuple[JsonShapedValue, ...]', value)
        return [thawed_json_value(item) for item in items]
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
        object.__setattr__(self, 'data', frozen_json_value(self.data))

    def to_json(self: Self) -> dict[str, Any]:
        """Return ``{'kind': kind, **data}`` as plain JSON types.

        Returns:
            The JSON-safe record.

        """
        return {KIND_FIELD: self.kind, **thawed_json_value(self.data)}

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
