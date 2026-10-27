"""The golden-trace harness: a game driven headless with scripted input, every sprite sampled.

A golden trace is the rect and visibility of every sprite in the active scene's ``all_sprites``,
recorded after each frame of a scripted, fully deterministic run (``record_trace``). The harness
knows a game only by its scene class and its input script (``InputScript``), so it runs any game
built on the engine: the ``record-golden-trace`` tool (glitchygames/replay/tools/registry.py)
runs it on the game it is given, with an input script named ``MODULE:NAME``
(``load_input_script``). Our own games' scripts and their golden traces are this repository's
(scripts/golden_inputs.py, scripts/record_golden_traces.py, tests/world/test_golden_traces.py).

Determinism:
    - Every frame runs with ``dt`` fixed at 1/60 second.
    - Every game is started with ``--random-seed`` (``RANDOM_SEED`` unless given): all the
      randomness a game draws from the engine's named streams (``glitchygames/randomness.py``)
      is fixed by it. Nothing is patched.
    - A game clock read from ``Scene.game_time`` is driven by the fixed dt (exactly 1/60 second
      per unpaused frame), so no clock is patched.
    - Save files go to a fresh temporary directory, so high scores on disk cannot leak in.
    - Events the host environment posts (window focus, window shown, audio devices, ...) are
      discarded before each frame. SDL's dummy video driver posts a focus-lost event at
      startup, which would auto-pause a game that pauses on focus loss.

Ids: each sprite gets ``<ClassName>#<n>`` the first time it is seen, where n counts that
class's sprites in order of first appearance over the whole run. Ids never renumber when a
sprite is removed (a collected coin, a dead ball).

Scope and maintenance:
    - ``GoldenTraceSceneManager.run_frame`` runs ``SceneManager._run_frame``, the same frame
      body ``SceneManager.start()`` runs (both branches, and the ``--record-trace`` hook).
    - Frame pacing, timing and the first frame's measured dt are out of scope: the harness
      fixes dt at 1/60 and never sleeps.

The trace format (gzip JSON Lines with keyframes and deltas, ``StableSpriteIds``, the reader and
writer) lives in ``glitchygames/tracing.py``; identical traces give identical bytes.

The harness never chooses the video driver: whoever runs it does (SDL's dummy drivers in the
tests and scripts/record_golden_traces.py, ``--headless`` on a game). Importing this module
imports the engine (``GameEngine``), so the tool table imports it only when the tool runs.

Moved from scripts/record_golden_traces.py (Stage D, Task D4a), re-keyed from our game keys to
a scene class and an input script.
"""

from __future__ import annotations

import contextlib
import importlib
import sys
import tempfile
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, Self, TypedDict, Unpack, override

import pygame

from glitchygames.engine import GameEngine
from glitchygames.engine_context import current_context
from glitchygames.events import AUDIO_EVENTS, WINDOW_EVENTS
from glitchygames.logical_names import logical_name
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes.scene import SCENE_MANAGERS_SLOT
from glitchygames.state import manager as save_manager_module
from glitchygames.testing.keys import qwerty_scancode
from glitchygames.tracing import StableSpriteIds, sample_scene_frame

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable, Iterator, Mapping

    from _typeshed import SupportsKeysAndGetItem

    from glitchygames.replay import ReplayResult

FRAME_SECONDS = 1.0 / 60.0
RANDOM_SEED = 20261018
# The header's ``source`` field for golden traces (scripts/record_golden_traces.py's and the
# record-golden-trace tool's)
GOLDEN_TRACE_SOURCE = 'golden-script'
SCREEN_RESOLUTION = '800x480'
# The program name the harness gives the engine's command line (sys.argv[0]), as the harness
# had when it was scripts/record_golden_traces.py: a game that reads its argv sees the same
HARNESS_PROGRAM_NAME = 'record_golden_traces'
# What separates an input script reference's module from its name (``MODULE:NAME``)
REFERENCE_SEPARATOR = ':'

# Events posted by the host environment rather than by the scripted player
ENVIRONMENT_EVENT_TYPES: tuple[int, ...] = (
    *WINDOW_EVENTS,
    *AUDIO_EVENTS,
    pygame.ACTIVEEVENT,
    pygame.VIDEOEXPOSE,
    pygame.VIDEORESIZE,
    pygame.JOYDEVICEADDED,
    pygame.JOYDEVICEREMOVED,
    pygame.CONTROLLERDEVICEADDED,
    pygame.CONTROLLERDEVICEREMOVED,
    pygame.KEYMAPCHANGED,
)


class InputScriptError(ValueError):
    """An input script reference (``MODULE:NAME``) that names no input script."""


class GameSceneClasses(MutableMapping[str, type[Scene]]):
    """Game key -> the game's scene class, each imported the first time it is looked up.

    A game is held as a reference, ``'<module>:<class>'``, until its first lookup imports the
    module (``importlib.import_module``) and keeps the class. Keys, length and membership import
    nothing, and neither do ``copy``, ``clear`` and ``update`` from another of these (which
    ``unittest.mock.patch.dict`` uses to register a stand-in game for one test): only a lookup
    imports a game.
    """

    def __init__(self: Self, entries: Mapping[str, str | type[Scene]]) -> None:
        """Hold the games.

        Args:
            entries: Game key -> its scene class, or a ``'<module>:<class>'`` reference to it.

        """
        self._entries: dict[str, str | type[Scene]] = dict(entries)

    @override
    def __getitem__(self: Self, game_key: str) -> type[Scene]:
        """Return a game's scene class, importing it on its first lookup.

        Args:
            game_key: The game.

        Returns:
            The scene class.

        Raises:
            TypeError: If the reference names something other than a Scene subclass.

        """
        entry = self._entries[game_key]
        if isinstance(entry, str):
            module_name, _, class_name = entry.partition(':')
            scene_class: object = getattr(importlib.import_module(module_name), class_name)
            if not isinstance(scene_class, type) or not issubclass(scene_class, Scene):
                message = f'{entry!r} is not a Scene subclass'
                raise TypeError(message)
            entry = scene_class
            self._entries[game_key] = entry
        return entry

    @override
    def __setitem__(self: Self, game_key: str, scene_class: type[Scene]) -> None:
        self._entries[game_key] = scene_class

    @override
    def __delitem__(self: Self, game_key: str) -> None:
        del self._entries[game_key]

    @override
    def __iter__(self: Self) -> Iterator[str]:
        return iter(self._entries)

    @override
    def __len__(self: Self) -> int:
        return len(self._entries)

    @override
    def __contains__(self: Self, game_key: object) -> bool:
        return game_key in self._entries

    @override
    def clear(self: Self) -> None:
        """Remove every game, importing none (the inherited clear looks each one up)."""
        self._entries.clear()

    def copy(self: Self) -> GameSceneClasses:
        """Return a new mapping of the same games, importing none.

        Returns:
            The copy: references stay references.

        """
        return GameSceneClasses(self._entries)

    @override
    def update(
        self: Self,
        other: SupportsKeysAndGetItem[str, type[Scene]] | Iterable[tuple[str, type[Scene]]] = (),
        /,
        **scene_classes: type[Scene],
    ) -> None:
        """Add games; another of these mappings' references are added unimported.

        Args:
            other: The games to add: a mapping or (game key, scene class) pairs.
            **scene_classes: More games, by key.

        """
        if isinstance(other, GameSceneClasses):
            self._entries.update(other._entries)
            other = ()
        super().update(other, **scene_classes)


class FrameObserver(Protocol):
    """Called after each recorded frame, to read more than the trace records (world data)."""

    def __call__(self, *, frame_number: int, scene: Scene, sprite_ids: StableSpriteIds) -> None:
        """Observe the active scene after a frame.

        Args:
            frame_number: The frame just run.
            scene: The active scene after the frame.
            sprite_ids: The run's sprite ids (the ids the trace uses).

        """
        ...


class RecordTraceHooks(TypedDict, total=False):
    """Optional callbacks into a ``record_trace`` run, given to it by keyword.

    Attributes:
        frame_observer: Called after each frame is sampled, with the same scene and sprite ids
            (the golden test reads world and camera positions through it).
        before_recording: Called with the game scene after it is installed and before
            recording starts (and before the first frame), e.g. to write a save the
            recording's header must hold.

    """

    frame_observer: FrameObserver | None
    before_recording: Callable[[Scene], None] | None


def press(key: int) -> pygame.event.Event:
    """Build a key-down event, at the key's US QWERTY position as a real keyboard reports it.

    Args:
        key: The pygame key code.

    Returns:
        The KEYDOWN event (its ``scancode`` from ``qwerty_scancode``: games bind positional
        controls by scancode).

    """
    return pygame.event.Event(
        pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=qwerty_scancode(key=key)
    )


def release(key: int) -> pygame.event.Event:
    """Build a key-up event, at the key's US QWERTY position as a real keyboard reports it.

    Args:
        key: The pygame key code.

    Returns:
        The KEYUP event (its ``scancode`` from ``qwerty_scancode``).

    """
    return pygame.event.Event(
        pygame.KEYUP, key=key, mod=0, unicode='', scancode=qwerty_scancode(key=key)
    )


@dataclass
class InputScript:
    """Scripted input for one game.

    Attributes:
        key_events: Frame number -> key events posted before that frame runs.
        placements: Frame number -> callables that adjust the active scene before that frame
            runs (used to put the player somewhere a short script cannot walk to).
        per_frame: Optional callable run before every frame; it returns extra events to post
            (a paddle tracking the ball).

    """

    key_events: dict[int, list[pygame.event.Event]] = field(default_factory=dict)
    placements: dict[int, list[Callable[[Scene], None]]] = field(default_factory=dict)
    per_frame: Callable[[Scene], list[pygame.event.Event]] | None = None

    def at(self, frame_number: int, *events: pygame.event.Event) -> None:
        """Post events before a frame.

        Args:
            frame_number: The frame the events are posted before.
            *events: The events to post.

        """
        self.key_events.setdefault(frame_number, []).extend(events)

    def tap(self, frame_number: int, key: int, *, held_frames: int) -> None:
        """Press a key before one frame and release it a number of frames later.

        Args:
            frame_number: The frame the key is pressed before.
            key: The pygame key code.
            held_frames: How many frames the key stays down.

        """
        self.at(frame_number, press(key))
        self.at(frame_number + held_frames, release(key))

    def place(self, frame_number: int, placement: Callable[[Scene], None]) -> None:
        """Adjust the active scene before a frame.

        Args:
            frame_number: The frame the placement runs before.
            placement: The callable that adjusts the scene.

        """
        self.placements.setdefault(frame_number, []).append(placement)


def load_input_script(*, reference: str) -> InputScript:
    """Build the input script a ``MODULE:NAME`` reference names (``--input-script``).

    The contract: ``NAME`` is a callable in module ``MODULE`` that takes no arguments and
    returns a fresh ``InputScript`` (as each of our games' builders in scripts/golden_inputs.py
    does: a script holds state, such as the keys a per-frame input holds, so each run builds its
    own). ``MODULE`` is imported with the current directory searched first, as ``python -m``
    and ``python -c`` search it, so a project's own module (``scripts.golden_inputs``, run from
    the repository root) is found from its console script too.

    Args:
        reference: ``MODULE:NAME``.

    Returns:
        The input script it builds.

    Raises:
        InputScriptError: If the reference is not ``MODULE:NAME``, its module does not import,
            it has no such name, the name is not callable, or the call returns something other
            than an ``InputScript``.

    """
    module_name, separator, name = reference.partition(REFERENCE_SEPARATOR)
    if not separator or not module_name or not name:
        message = f'{reference!r} is not MODULE:NAME'
        raise InputScriptError(message)
    current_directory = str(Path.cwd())
    searched_first = current_directory not in sys.path
    if searched_first:
        sys.path.insert(0, current_directory)
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        message = f'{reference!r}: module {module_name!r} does not import ({error})'
        raise InputScriptError(message) from error
    finally:
        if searched_first:
            sys.path.remove(current_directory)
    builder: object = getattr(module, name, None)
    if not callable(builder):
        message = f'{reference!r}: {module_name} has no callable {name!r}'
        raise InputScriptError(message)
    script: object = builder()
    if not isinstance(script, InputScript):
        message = f'{reference!r} returned a {type(script).__name__}, not an InputScript'
        raise InputScriptError(message)
    return script


@contextlib.contextmanager
def deterministic_environment(*, save_root: Path) -> Generator[None]:
    """Replace the save directory, then restore it.

    Randomness needs no replacement: ``_start_game`` passes ``--random-seed``. Clocks need
    none either: a game clock read from Scene.game_time is driven by the harness's fixed dt.

    Args:
        save_root: Directory the games' save files go to.

    Yields:
        None, while the replacements are in place.

    """

    def temporary_save_directory(app_name: str) -> Path:
        return save_root / app_name

    replacements: list[tuple[object, str, object]] = [
        (save_manager_module, 'get_save_directory', temporary_save_directory),
    ]
    originals = [(owner, name, getattr(owner, name)) for owner, name, _ in replacements]
    try:
        for owner, name, replacement in replacements:
            setattr(owner, name, replacement)
        yield
    finally:
        for owner, name, original in originals:
            setattr(owner, name, original)


@contextlib.contextmanager
def command_line(arguments: list[str]) -> Generator[None]:
    """Temporarily replace sys.argv (GameEngine parses it at construction).

    Args:
        arguments: The arguments after the program name (``HARNESS_PROGRAM_NAME``).

    Yields:
        None, while sys.argv holds the arguments.

    """
    original_arguments = sys.argv
    sys.argv = [HARNESS_PROGRAM_NAME, *arguments]
    try:
        yield
    finally:
        sys.argv = original_arguments


class GoldenTraceSceneManager(SceneManager):
    """The engine's SceneManager plus a frame step without pacing, timing or FPS events.

    It adds methods only, so a game runs exactly as it does under SceneManager.start().
    """

    @classmethod
    def install(cls) -> GoldenTraceSceneManager:
        """Make a fresh instance the SceneManager singleton (GameEngine then adopts it).

        Returns:
            The new scene manager.

        """
        SceneManager._reset()
        cls._reset()
        manager = cls()
        # Stored as the current engine context's entry for SceneManager in the scene managers
        # slot, so a plain SceneManager() call answers with it too
        current_context().value(slot=SCENE_MANAGERS_SLOT)[SceneManager] = manager
        return manager

    @classmethod
    def uninstall(cls) -> None:
        """Clear the singleton so the next game starts from a fresh scene manager."""
        SceneManager._reset()
        cls._reset()

    def run_frame(self) -> None:
        """Run one frame the way SceneManager.start() does, without pacing or timing."""
        self._run_frame()


class GoldenTraceEngine(GameEngine):
    """The GameEngine, started without its frame loop so the recorder can step frames."""

    @override
    def initialize_display(self) -> None:
        """Open a plain window: no SCALED or FULLSCREEN flag.

        SDL's dummy video driver has no renderer for SCALED, so pygame warns "no fast renderer
        available" (an error under pytest's filterwarnings). The recorder never shows the
        window, and the flags do not change any sprite's rect.
        """
        self.mode_flags = 0
        super().initialize_display()

    def install_game(self, *, scene_class: type[Scene]) -> None:
        """Create the game scene and make it active, as GameEngine.start() does.

        Mirrors GameEngine.start() up to, not including, the timer backend and frame loop.

        Args:
            scene_class: The game's scene class.

        """
        game = scene_class(options=GameEngine.OPTIONS)
        self.game = game
        SceneManager.OPTIONS = GameEngine.OPTIONS
        self.scene_manager.game_engine = self
        self._initialize_event_managers()
        self.scene_manager.switch_to_scene(game)


def _start_game(
    *, scene_class: type[Scene], random_seed: int, extra_arguments: list[str] | None = None
) -> GoldenTraceSceneManager:
    """Construct the game engine and install the game's scene.

    Args:
        scene_class: The game's scene class.
        random_seed: The run's master seed (``--random-seed``).
        extra_arguments: More command-line arguments (``--replay-trace PATH``).

    Returns:
        The scene manager with the game scene active.

    """
    manager = GoldenTraceSceneManager.install()
    with command_line([
        '--windowed',
        '--resolution',
        SCREEN_RESOLUTION,
        '--log-level',
        'warning',
        '--input-mode',
        'joystick',
        '--random-seed',
        str(random_seed),
        *(extra_arguments or []),
    ]):
        engine = GoldenTraceEngine(game=scene_class)
    assert engine.scene_manager is manager
    engine.install_game(scene_class=scene_class)
    return manager


@contextlib.contextmanager
def golden_game(
    *, scene_class: type[Scene], random_seed: int, extra_arguments: list[str] | None = None
) -> Generator[GoldenTraceSceneManager]:
    """Start a game in the harness with temporary saves; tear it all down afterwards.

    Args:
        scene_class: The game's scene class.
        random_seed: The run's master seed (``--random-seed``).
        extra_arguments: More command-line arguments (``--replay-trace PATH``).

    Yields:
        The scene manager with the game scene active.

    """
    with (
        tempfile.TemporaryDirectory(prefix='golden-trace-saves-') as save_directory,
        deterministic_environment(save_root=Path(save_directory)),
    ):
        manager = _start_game(
            scene_class=scene_class, random_seed=random_seed, extra_arguments=extra_arguments
        )
        try:
            yield manager
        finally:
            engine = manager.game_engine
            if engine is not None:
                engine.stop_trace_recording()
            pygame.event.clear()
            GoldenTraceSceneManager.uninstall()


def discard_environment_events() -> None:
    """Drop events the host environment posted; keep the rest in order.

    ``pygame.event.get(eventtype=...)`` does not return pygame-ce's window events (they are
    split out of SDL's single window event only by an unfiltered get), so the whole queue is
    drained and every non-environment event is posted again.
    """
    kept_events = [
        event for event in pygame.event.get() if event.type not in ENVIRONMENT_EVENT_TYPES
    ]
    for event in kept_events:
        pygame.event.post(event)


def record_trace(
    *,
    scene_class: type[Scene],
    script: InputScript,
    frame_count: int,
    recording_path: Path | None = None,
    random_seed: int = RANDOM_SEED,
    **hooks: Unpack[RecordTraceHooks],
) -> dict[str, Any]:
    """Run a game headless with its scripted input and record every sprite each frame.

    Args:
        scene_class: The game's scene class.
        script: Its input script (a fresh one: a per-frame input holds state across frames).
        frame_count: How many frames to run.
        recording_path: If given, the engine also records the run there as ``--record-trace``
            would (GameEngine.start_trace_recording), for checking recordings against the
            harness's own frames.
        random_seed: The run's master seed, passed as ``--random-seed``.
        **hooks: Optional callbacks into the run, by keyword (``RecordTraceHooks``).

    Returns:
        The trace: the game (the scene class's logical name,
        ``glitchygames.logical_names.logical_name``), frame seconds and one record per frame.
        A caller that names its games otherwise sets ``game`` itself (our golden traces name
        theirs by game key: scripts/record_golden_traces.py).

    """
    frame_observer = hooks.get('frame_observer')
    before_recording = hooks.get('before_recording')
    frames: list[dict[str, Any]] = []
    sprite_ids = StableSpriteIds()
    with golden_game(scene_class=scene_class, random_seed=random_seed) as manager:
        engine = manager.game_engine
        assert engine is not None
        if before_recording is not None:
            assert manager.active_scene is not None
            before_recording(manager.active_scene)
        if recording_path is not None:
            engine.start_trace_recording(path=recording_path)
        for frame_number in range(frame_count):
            manager.dt = FRAME_SECONDS
            discard_environment_events()
            assert manager.active_scene is not None
            for placement in script.placements.get(frame_number, []):
                placement(manager.active_scene)
            if script.per_frame is not None:
                for event in script.per_frame(manager.active_scene):
                    pygame.event.post(event)
            for event in script.key_events.get(frame_number, []):
                pygame.event.post(event)
            manager.run_frame()
            frames.append(
                sample_scene_frame(
                    frame_number=frame_number,
                    scene=manager.active_scene,
                    sprite_ids=sprite_ids,
                )
            )
            if frame_observer is not None:
                frame_observer(
                    frame_number=frame_number,
                    scene=manager.active_scene,
                    sprite_ids=sprite_ids,
                )
    return {
        'game': logical_name(scene_class=scene_class),
        'frame_seconds': FRAME_SECONDS,
        'frames': frames,
    }


def replay_golden_recording(
    *, scene_class: type[Scene], script: InputScript, path: Path, frame_limit: int | None = None
) -> ReplayResult:
    """Replay a recording made by record_trace(recording_path=...) through the harness.

    Key events and per-frame input come from the recording (the replay's event pump), so they
    are not posted again. The script's placements are not input: they move sprites directly,
    like a supervisor, so they are applied again on the same frames, before the frame runs, as
    record_trace applies them. (A placement that posts events, such as a key release before a
    pause, posts real events the replay drops: the recording serves them.)

    The result is settled as GameEngine._shutdown settles it (``finish_run``): a harness that
    stops before the recording's last frame reports a length divergence.

    Args:
        scene_class: The game's scene class.
        script: The input script the recording was made with (its placements are applied).
        path: The recording.
        frame_limit: Stop after this many frames even if the replay goes on (None: run until
            the replay stops).

    Returns:
        The replay's result.

    """
    # Headless: a watched replay would pause at its end (or divergence) instead of stopping
    with golden_game(
        scene_class=scene_class,
        random_seed=RANDOM_SEED,
        extra_arguments=['--replay-trace', str(path), '--headless'],
    ) as manager:
        engine = manager.game_engine
        assert engine is not None
        sources = engine.replay_sources
        assert sources is not None
        frame_number = 0
        while (
            not sources.stop_requested
            and manager.active_scene is not None
            and (frame_limit is None or frame_number < frame_limit)
        ):
            # The harness steps frames without start()/_finish_frame, so it asks the frame-time
            # door itself: the first call returns frame 0's dt, each later call the next frame's
            manager.dt = sources.frame_seconds(measured=FRAME_SECONDS)
            for placement in script.placements.get(frame_number, []):
                placement(manager.active_scene)
            manager.run_frame()
            frame_number += 1
        sources.finish_run()
    return sources.result
