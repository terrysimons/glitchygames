"""How each scene began, so it can be rebuilt from its start for in-game playback.

A scene's start (``SceneStart``) is what rebuilding it as it began needs
(plans/2026-10-19-gameplay-replay.md, section 5.1): its class, ``Scene.replay_arguments()``,
every random stream's state and the frame clock as its ``__init__`` began, and the save view
(``save_namespace_snapshot`` of every store the doors opened) as its first ``setup()`` began.

Rules:

1. Capture happens only while it can be used (``scene_start_capture_enabled``): while the active
   doors capture scene starts (``EngineSources.captures_scene_starts``: a run recorded with
   ``--record-trace`` from its start, a ``--rebaseline`` replay, and Part 3's playback scope), or
   when the scene class opts into instant replay (``INSTANT_REPLAY_SECONDS`` is not None).
   Otherwise nothing is captured and live play pays nothing.
2. ``Scene.__init__`` begins the capture as its first statement (``begin_scene_start_capture``):
   the stream states and the frame clock, before a subclass's ``__init__`` draws anything after
   its ``super().__init__()``. A subclass that draws before calling ``super().__init__()`` is not
   rebuilt exactly.
3. The scene manager completes the capture before the scene's **first** ``setup()``
   (``SceneStartCapture.complete``, from ``SceneManager._setup_new_scene``); later setups (resuming
   from the pause screen) keep the first start. ``replay_arguments()`` must be JSON-safe: it must
   read back from JSON exactly as returned (so no tuples, non-string keys, NaN or objects), else a
   ``TypeError`` naming the scene is raised.
4. ``rebuild_scene`` restores the streams and the frame clock, then constructs the scene class
   with the recorded arguments and the given options; it does not call ``setup()`` (the playback
   scope does, as the scene manager would).
5. A recording writes each start as its frame field ``scene_start`` (``SceneStart.to_json``;
   glitchygames/recording.py documents the format).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict

from glitchygames.randomness import capture_stream_states, restore_stream_states
from glitchygames.sources import active_sources, frame_clock_seconds, set_frame_clock_seconds
from glitchygames.state.sandbox import save_namespace_snapshot

if TYPE_CHECKING:
    from glitchygames.scenes import Scene


class SceneStart(BaseModel):
    """How one scene began (read-only; see the module docstring).

    Attributes:
        scene_class: The scene's class name (``type(scene).__name__``).
        arguments: ``Scene.replay_arguments()``, JSON-safe.
        random_states: ``capture_stream_states()`` as the scene's ``__init__`` began.
        frame_clock_seconds: The frame clock as the scene's ``__init__`` began.
        saves: Save namespace -> ``save_namespace_snapshot`` of its store, as the scene's first
            ``setup()`` began (slot name -> envelope).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    scene_class: str
    arguments: dict[str, Any]
    random_states: dict[str, Any]
    frame_clock_seconds: float
    saves: dict[str, dict[str, Any]]

    def to_json(self: Self) -> dict[str, Any]:
        """Return the start as plain JSON types (a recording's ``scene_start`` field).

        Returns:
            The JSON-safe record.

        """
        return self.model_dump()

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> SceneStart:
        """Read a record written by ``to_json``.

        Args:
            record: A record written by ``to_json``.

        Returns:
            The start.

        """
        return cls.model_validate(record)


class SceneStartCapture:
    """One scene's start while it is being captured: begun in ``__init__``, completed at setup.

    Attributes:
        random_states: ``capture_stream_states()`` as the scene's ``__init__`` began.
        frame_clock_seconds: The frame clock at the same moment.
        start: The completed start, or None before the scene's first setup.

    """

    def __init__(self: Self, *, random_states: dict[str, Any], frame_clock_seconds: float) -> None:
        """Hold what the scene's ``__init__`` captured.

        Args:
            random_states: ``capture_stream_states()``.
            frame_clock_seconds: The frame clock.

        """
        self.random_states = random_states
        self.frame_clock_seconds = frame_clock_seconds
        self.start: SceneStart | None = None

    def complete(self: Self, *, scene: Scene) -> SceneStart:
        """Complete the start before the scene's first setup; later calls keep the first.

        Args:
            scene: The scene being set up (the one whose ``__init__`` began this capture).

        Returns:
            The start.

        Raises:
            TypeError: If ``scene.replay_arguments()`` is not JSON-safe (the message names the
                scene's class).

        """
        if self.start is not None:
            return self.start
        scene_class_name = type(scene).__name__
        arguments = scene.replay_arguments()
        try:
            arguments_read_back = json.loads(json.dumps(arguments, allow_nan=False))
        except (TypeError, ValueError) as error:
            message = f'{scene_class_name}.replay_arguments() is not JSON-safe: {error}'
            raise TypeError(message) from error
        if arguments_read_back != arguments:
            message = (
                f'{scene_class_name}.replay_arguments() does not read back from JSON as '
                f'returned (tuples, non-string keys?): {arguments!r}'
            )
            raise TypeError(message)
        saves = {
            namespace: save_namespace_snapshot(saves=store)
            for namespace, store in active_sources().opened_save_namespaces.items()
        }
        self.start = SceneStart(
            scene_class=scene_class_name,
            arguments=arguments_read_back,
            random_states=self.random_states,
            frame_clock_seconds=self.frame_clock_seconds,
            saves=saves,
        )
        return self.start


def scene_start_capture_enabled(*, scene_class: type[Scene]) -> bool:
    """Return whether a scene of ``scene_class`` constructed now captures its start (rule 1).

    Args:
        scene_class: The scene's class.

    Returns:
        True while the active doors capture scene starts or the class opts into instant replay.

    """
    # Declared on Scene by Part 3's instant replay (Task 5); until then read with a default
    if getattr(scene_class, 'INSTANT_REPLAY_SECONDS', None) is not None:
        return True
    return active_sources().captures_scene_starts


def begin_scene_start_capture(*, scene_class: type[Scene]) -> SceneStartCapture | None:
    """Begin a scene's start capture, when enabled (``Scene.__init__``'s first statement).

    Args:
        scene_class: The scene's class.

    Returns:
        The capture, or None when capture is not enabled (rule 1).

    """
    if not scene_start_capture_enabled(scene_class=scene_class):
        return None
    return SceneStartCapture(
        random_states=capture_stream_states(), frame_clock_seconds=frame_clock_seconds()
    )


def rebuild_scene(*, start: SceneStart, scene_class: type[Scene], options: dict[str, Any]) -> Scene:
    """Rebuild a scene as it began (rule 4): streams, frame clock, then its constructor.

    Args:
        start: The scene's start.
        scene_class: The class ``start.scene_class`` names.
        options: The options the rebuilt scene is constructed with.

    Returns:
        The rebuilt scene, not set up.

    """
    restore_stream_states(states=start.random_states)
    set_frame_clock_seconds(seconds=start.frame_clock_seconds)
    return scene_class(**start.arguments, options=options)
