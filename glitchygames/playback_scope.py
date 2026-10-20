"""The records of an in-game playback scope, shared by the scene manager and the replay package.

A playback scope (glitchygames/replay/playback.py, whose docstring is the contract) plays a
recording to a scene rebuilt from its start while the live game waits. ``start_playback``
builds a ``PlaybackRequest``; the scene manager enters it at the start of the next frame
(``SceneManager.request_playback``) and keeps a ``PlaybackSession`` until the scope ends.

This module is a leaf like glitchygames/sources.py: it imports no package module at run time
(the types it names are imported for type checking only), so glitchygames.scenes imports it
without pulling in the replay package.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Final, Literal

if TYPE_CHECKING:
    from glitchygames.replay.playback import PlaybackSources
    from glitchygames.scene_start import SceneStart
    from glitchygames.scenes import Scene

# What a scope plays: an attract-mode demo, or an instant replay of the live scene
type PlaybackKind = Literal['demo', 'instant']
DEMO_PLAYBACK: Final = 'demo'
INSTANT_PLAYBACK: Final = 'instant'


@dataclasses.dataclass(frozen=True)
class PlaybackRequest:
    """A playback scope to enter at the start of the next frame (read-only).

    A dataclass rather than a pydantic model: it holds live objects (sources, scenes), not data.

    Attributes:
        sources: The scoped doors the playback runs on.
        start: The start of the scene to rebuild (the ``scene_start`` the first played frame
            holds).
        scene_class: The class ``start.scene_class`` names.
        then: The scene to make active when the scope ends.
        kind: What the scope plays.
        frame_count: How many recorded frames the scope plays at most (from its first played
            frame to the recording's end); the ``playback`` control event's ``frames``.

    """

    sources: PlaybackSources
    start: SceneStart
    scene_class: type[Scene]
    then: Scene
    kind: PlaybackKind
    frame_count: int


@dataclasses.dataclass(frozen=True)
class PlaybackSession:
    """A playback scope in progress: what it runs on and what its end restores (read-only).

    Attributes:
        sources: The scoped doors pushed for the scope.
        live_scene: The scene that was active when the scope began, stashed without
            ``cleanup()`` and never touched while the scope runs.
        then: The scene to make active when the scope ends.
        kind: What the scope plays.
        saved_random_states: ``capture_stream_states()`` as the scope began.
        saved_frame_clock_seconds: The frame clock as the scope began.
        saved_fps_event_seconds: When the live game last posted an FPS event
            (``SceneManager._previous_fps_event_seconds``), on the live frame clock.

    """

    sources: PlaybackSources
    live_scene: Scene
    then: Scene
    kind: PlaybackKind
    saved_random_states: dict[str, Any]
    saved_frame_clock_seconds: float
    saved_fps_event_seconds: float
