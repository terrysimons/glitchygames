"""How each scene began, so it can be rebuilt from its start for in-game playback.

A scene's start (``SceneStart``) is what rebuilding it as it began needs
(plans/2026-10-19-gameplay-replay.md, section 5.1): its class (module and qualified name),
``Scene.replay_arguments()``, every
random stream's state and the frame clock at two moments (as its ``__init__`` began, and as its
first ``setup()`` began), and the save view as its ``__init__`` began.

Rules:

1. Capture happens only while it can be used (``scene_start_capture_enabled``): never for a scene
   class with ``CAPTURES_SCENE_START = False`` (one that cannot be rebuilt on its own, such as
   ``PauseScene``, which presents another scene); otherwise while the active doors capture scene
   starts (``EngineSources.captures_scene_starts``: a run recorded with ``--record-trace`` from
   its start, a ``--rebaseline`` replay, while recording, and Part 3's playback scope), or when
   the scene class opts into instant replay (``INSTANT_REPLAY_SECONDS`` is not None). Otherwise
   nothing is captured and live play pays nothing.
2. ``Scene.__init__`` begins the capture as its first statement (``begin_scene_start_capture``):
   the stream states and the frame clock, before a subclass's ``__init__`` draws anything after
   its ``super().__init__()`` (a subclass that draws before calling it is not rebuilt exactly),
   and a snapshot of every save store already open. A store first opened while the capture is
   pending (inside ``__init__``, or before the first setup) is snapshotted as it is opened, before
   the game can write to it (``glitchygames.state.open_saves`` tells the pending captures). So the
   save view is the saves as they were before the scene's ``__init__`` ran.
3. The scene manager completes the capture before the scene's **first** ``setup()``
   (``SceneStartCapture.complete``, from ``SceneManager._setup_new_scene``): the stream states and
   frame clock again, since other code may draw or frame time may pass between building a scene
   and setting it up (a transition builds the next floor a frame early), and
   ``replay_arguments()``, which must read back from JSON exactly as returned (no tuples,
   non-string keys, NaN or objects), else a ``TypeError`` naming the scene is raised. Later
   setups (resuming from the pause screen) keep the first start.
4. ``rebuild_scene`` restores the construction-time streams and frame clock, constructs the scene
   class with the recorded arguments and the given options, then restores the setup-time streams
   and frame clock; it does not call ``setup()``. It sets the global random streams and frame
   clock: the caller (the playback scope) saves them before and restores them after playback.
5. A ``SceneStart`` shares no mutable state with its capture or callers: the capture builds it
   from deep copies, ``to_json`` returns a deep copy, ``from_json`` reads one, and
   ``rebuild_scene`` passes a deep copy of the arguments. Its own dicts must not be changed.
6. A recording writes each start as its frame field ``scene_start`` (``SceneStart.to_json``;
   glitchygames/recording.py documents the format), on the scene's first logic frame (rule 7):
   a start without one is never written.
7. The first logic frame (``FirstLogicFrame``): the first frame whose ``dt_tick`` runs on the
   scene. A scene set up between frames (a run's first scene) begins logic on the next frame; a
   scene set up inside a frame (a ``next_scene`` switch at the frame's end) on the frame after;
   a scene that arrived by a transition after the ride (``_capture_arriving_scene`` ran one
   ``dt_tick(0.001)`` on it as the ride began, and the ride's frames run no logic). At the top
   of that frame, before any of its work, the scene manager completes the start with the state
   the scene's logic began in (``SceneStartCapture.begin_first_logic_frame``): every random
   stream's state, the frame clock (the setup clock plus any frame time since), the FPS event
   timer (``SceneManager._previous_fps_event_seconds``), how many of the code-posted events
   pending then (posted before the frame began, by whatever code ran before: an FPS event the
   previous frame's end posted, a post of the scene left) the frame's first pump delivers
   (``earlier_internal_event_count``; counted from the internal-post tracker, so exact while
   posts are tracked: while recording or replaying, and from the first setup of a scene that
   keeps an instant-replay journal, glitchygames/instant_replay.py), and whether the scene
   arrived by a
   transition. A playback starts there (glitchygames/replay/playback.py): it sets the scene up,
   repeats the transition's arrival step for a scene that arrived by one, then restores that
   state, and serves those earlier events from the recording instead of comparing them.

This module is a leaf like glitchygames/sources.py: it imports only pydantic and the leaves
(glitchygames.randomness, glitchygames.sources, glitchygames.state), so glitchygames.scenes and
glitchygames.recording import it without pulling in the replay package.
"""

from __future__ import annotations

import copy
import json
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, Field

from glitchygames.randomness import capture_stream_states, restore_stream_states
from glitchygames.sources import (
    active_sources,
    frame_clock_seconds,
    observe_save_store_openings,
    set_frame_clock_seconds,
    stop_observing_save_store_openings,
)
from glitchygames.state.sandbox import save_namespace_snapshot

if TYPE_CHECKING:
    from glitchygames.scenes import Scene
    from glitchygames.state.manager import SaveManager


class FirstLogicFrame(BaseModel):
    """The state a scene's first logic frame began in (read-only; rule 7).

    Attributes:
        random_states: ``capture_stream_states()`` at the top of the frame.
        frame_clock_seconds: The frame clock at the top of the frame.
        fps_event_seconds: When the last FPS event was posted, on the frame clock.
        earlier_internal_event_count: How many code-posted events pending at the top of the
            frame its first pump delivers (posted before the frame, so not by the scene's
            logic).
        arrived_by_transition: True when the scene arrived by a transition (its arrival step
            ran a ``dt_tick`` on it and snapped its camera).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    random_states: dict[str, Any]
    frame_clock_seconds: float
    fps_event_seconds: float
    earlier_internal_event_count: int = Field(ge=0)
    arrived_by_transition: bool


class SceneStart(BaseModel):
    """How one scene began (read-only; see the module docstring).

    Attributes:
        scene_class: The scene's class name (``type(scene).__qualname__``; older recordings hold
            ``__name__``, the same for a class defined at a module's top level).
        scene_module: The module the scene's class is defined in (``type(scene).__module__``),
            so two loaded classes of the same name are told apart; None in recordings made
            before starts held it.
        arguments: ``Scene.replay_arguments()``, JSON-safe.
        construction_random_states: ``capture_stream_states()`` as the scene's ``__init__``
            began.
        construction_frame_clock_seconds: The frame clock as the scene's ``__init__`` began.
        setup_random_states: ``capture_stream_states()`` as the scene's first ``setup()``
            began.
        setup_frame_clock_seconds: The frame clock as the scene's first ``setup()`` began.
        saves: Save namespace -> ``save_namespace_snapshot`` of its store (slot name ->
            envelope) as the scene's ``__init__`` began, or as it was first opened after that.
        first_logic_frame: The state the scene's first logic frame began in (rule 7), or None
            until that frame begins (a start without it cannot be played).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    scene_class: str
    scene_module: str | None = None
    arguments: dict[str, Any]
    construction_random_states: dict[str, Any]
    construction_frame_clock_seconds: float
    setup_random_states: dict[str, Any]
    setup_frame_clock_seconds: float
    saves: dict[str, dict[str, Any]]
    first_logic_frame: FirstLogicFrame | None = None

    def to_json(self: Self) -> dict[str, Any]:
        """Return the start as plain JSON types (a recording's ``scene_start`` field).

        Returns:
            A deep copy: changing it never changes this start.

        """
        return copy.deepcopy(self.model_dump())

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> SceneStart:
        """Read a record written by ``to_json``.

        Args:
            record: A record written by ``to_json`` (copied: changing it later changes nothing).

        Returns:
            The start.

        """
        return cls.model_validate(copy.deepcopy(record))


class SceneStartCapture:
    """One scene's start while it is being captured: begun in ``__init__``, completed at setup.

    While pending it observes save stores opened (``on_save_store_opened``), snapshotting each
    store it has not seen yet (rule 2).

    Attributes:
        construction_random_states: ``capture_stream_states()`` as the scene's ``__init__``
            began.
        construction_frame_clock_seconds: The frame clock at the same moment.
        saves: Namespace -> snapshot, as each store was before the scene's ``__init__`` ran.
        start: The completed start, or None before the scene's first setup (its
            ``first_logic_frame`` is added as that frame begins).
        arrived_by_transition: True once the scene arrived by a transition (rule 7).

    """

    def __init__(
        self: Self,
        *,
        construction_random_states: dict[str, Any],
        construction_frame_clock_seconds: float,
        saves: dict[str, dict[str, Any]],
    ) -> None:
        """Hold what the scene's ``__init__`` captured.

        Args:
            construction_random_states: ``capture_stream_states()``.
            construction_frame_clock_seconds: The frame clock.
            saves: Snapshots of the save stores already open.

        """
        self.construction_random_states = construction_random_states
        self.construction_frame_clock_seconds = construction_frame_clock_seconds
        self.saves = saves
        self.start: SceneStart | None = None
        # Set by SceneManager._start_transition for a scene that arrives by a transition
        self.arrived_by_transition = False

    def on_save_store_opened(self: Self, *, namespace: str, store: SaveManager) -> None:
        """Snapshot a store opened while pending, unless an earlier snapshot holds it.

        Args:
            namespace: The store's namespace.
            store: The store, not yet written to by whoever opened it.

        """
        if self.start is None and namespace not in self.saves:
            self.saves[namespace] = save_namespace_snapshot(saves=store)

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
        stop_observing_save_store_openings(observer=self)
        self.start = SceneStart(
            scene_class=type(scene).__qualname__,
            scene_module=type(scene).__module__,
            arguments=arguments_read_back,
            construction_random_states=copy.deepcopy(self.construction_random_states),
            construction_frame_clock_seconds=self.construction_frame_clock_seconds,
            setup_random_states=capture_stream_states(),
            setup_frame_clock_seconds=frame_clock_seconds(),
            saves=copy.deepcopy(self.saves),
        )
        return self.start

    def begin_first_logic_frame(
        self: Self, *, fps_event_seconds: float, earlier_internal_event_count: int
    ) -> None:
        """Complete the start with the state its first logic frame begins in (rule 7).

        Called at the top of every frame that runs the scene's logic; only the first (after
        its setup) adds anything.

        Args:
            fps_event_seconds: When the last FPS event was posted, on the frame clock.
            earlier_internal_event_count: How many code-posted events are pending now.

        """
        if self.start is None or self.start.first_logic_frame is not None:
            return
        self.start = self.start.model_copy(
            update={
                'first_logic_frame': FirstLogicFrame(
                    random_states=capture_stream_states(),
                    frame_clock_seconds=frame_clock_seconds(),
                    fps_event_seconds=fps_event_seconds,
                    earlier_internal_event_count=earlier_internal_event_count,
                    arrived_by_transition=self.arrived_by_transition,
                )
            }
        )


def scene_start_capture_enabled(*, scene_class: type[Scene]) -> bool:
    """Return whether a scene of ``scene_class`` constructed now captures its start (rule 1).

    Args:
        scene_class: The scene's class.

    Returns:
        False for a class that opts out; else True while the active doors capture scene starts
        or the class opts into instant replay.

    """
    if not scene_class.CAPTURES_SCENE_START:
        return False
    # Its instant-replay journal begins at its start (glitchygames/instant_replay.py)
    if scene_class.INSTANT_REPLAY_SECONDS is not None:
        return True
    return active_sources().captures_scene_starts


def begin_scene_start_capture(*, scene_class: type[Scene]) -> SceneStartCapture | None:
    """Begin a scene's start capture, when enabled (``Scene.__init__``'s first statement).

    Args:
        scene_class: The scene's class.

    Returns:
        The capture, observing save stores opened until it completes, or None when capture is
        not enabled (rule 1).

    """
    if not scene_start_capture_enabled(scene_class=scene_class):
        return None
    capture = SceneStartCapture(
        construction_random_states=capture_stream_states(),
        construction_frame_clock_seconds=frame_clock_seconds(),
        saves={
            namespace: save_namespace_snapshot(saves=store)
            for namespace, store in active_sources().opened_save_namespaces.items()
        },
    )
    observe_save_store_openings(observer=capture)
    return capture


def rebuild_scene(*, start: SceneStart, scene_class: type[Scene], options: dict[str, Any]) -> Scene:
    """Rebuild a scene as it began, ready for its setup (rule 4).

    Sets the global random streams and frame clock (the caller restores them afterwards): the
    construction-time ones, then the constructor runs, then the setup-time ones, so the caller's
    ``setup()`` draws and reads what the original's did.

    Args:
        start: The scene's start.
        scene_class: The class ``start.scene_class`` names.
        options: The options the rebuilt scene is constructed with.

    Returns:
        The rebuilt scene, not set up.

    """
    restore_stream_states(states=start.construction_random_states)
    set_frame_clock_seconds(seconds=start.construction_frame_clock_seconds)
    scene = scene_class(**copy.deepcopy(start.arguments), options=options)
    restore_stream_states(states=start.setup_random_states)
    set_frame_clock_seconds(seconds=start.setup_frame_clock_seconds)
    return scene
