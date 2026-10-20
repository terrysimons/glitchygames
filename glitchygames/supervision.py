"""The supervisor hook and control events.

A supervisor is called once per frame at a fixed place in the frame (after logic and events,
before frame services, camera aim and positioning — see SceneManager._run_scene_frame), so what
it reads is the frame's final logic state and what it changes is drawn this frame and seen by
collision next frame. Replay controls and recorded breakpoints use it today; a future cheat device
plugs in here (plans/2026-10-19-gameplay-replay.md, section 2).

A control event is a supervisor action recorded with the frame it happened in; a replay
re-applies recorded control events on the same frame, so sessions with supervisor actions replay
exactly.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Protocol, Self

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
        """Inspect or act on the frame ``frame_number`` of ``scene`` (None between scenes)."""
        ...


@dataclasses.dataclass(frozen=True)
class ControlEvent:
    """A recorded supervisor action: its kind and JSON-safe data."""

    kind: str
    data: dict[str, Any]

    def to_json(self: Self) -> dict[str, Any]:
        """Return ``{'kind': kind, **data}``.

        Returns:
            The JSON-safe record.

        """
        return {KIND_FIELD: self.kind, **self.data}

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> ControlEvent:
        """Read a record written by ``to_json``.

        Args:
            record: A record written by ``to_json``.

        Returns:
            The control event.

        """
        data = {name: value for name, value in record.items() if name != KIND_FIELD}
        return cls(kind=str(record[KIND_FIELD]), data=data)
