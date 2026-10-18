"""Record golden traces of every example game, driven headless with scripted input.

A golden trace is the rect and visibility of every sprite in the active scene's
``all_sprites``, recorded after each frame of a scripted, fully deterministic run. The
traces in ``tests/world/golden/`` were recorded before the engine world-space change
(plans/2026-10-18-engine-world-space.md); ``tests/world/test_golden_traces.py`` replays the
same scripts and fails on any difference that is not listed and justified there.

Determinism:
    - Every frame runs with ``dt`` fixed at 1/60 second.
    - Randomness the games use (``secrets.randbelow`` in PaddleSlap, the ball serve's
      ``_SERVE_RANDOM``, and the shake effects' ``secrets.SystemRandom``) is replaced by one
      ``random.Random`` seeded with ``RANDOM_SEED``.
    - PaddleSlap's clock reads (``time.perf_counter`` for its seed, ``time.time`` for the ball
      spawn cooldown) come from a fake clock that advances exactly 1/60 second per frame.
    - Save files go to a fresh temporary directory, so high scores on disk cannot leak in.
    - Events the host environment posts (window focus, window shown, audio devices, ...) are
      discarded before each frame. SDL's dummy video driver posts a focus-lost event at
      startup, which would auto-pause Clockwork Keep.

Ids: each sprite gets ``<ClassName>#<n>`` the first time it is seen, where n counts that
class's sprites in order of first appearance over the whole run. Ids never renumber when a
sprite is removed (a collected coin, a dead ball).

Scope and maintenance:
    - ``GoldenTraceSceneManager.run_frame`` copies the transition branch of
      ``SceneManager.start()`` (the non-transition branch is ``_run_scene_frame``, shared with
      start()). Keep the copy in sync when start()'s transition branch changes.
    - Frame pacing, timing and the first frame's measured dt are out of scope: the harness
      fixes dt at 1/60 and never sleeps. Their tests live elsewhere (Task 5 of the plan).

The trace format (gzip JSON Lines with keyframes and deltas, ``StableSpriteIds``, the
reader and writer) lives in ``glitchygames/tracing.py``; identical traces give identical
bytes.

Usage:
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python scripts/record_golden_traces.py
"""

from __future__ import annotations

import contextlib
import os
import random
import sys
import tempfile
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from glitchygames.effects import shake as shake_module
from glitchygames.engine import GameEngine
from glitchygames.events import AUDIO_EVENTS, WINDOW_EVENTS
from glitchygames.examples import paddleslap
from glitchygames.examples.brave_adventurer.game import BraveAdventurerScene
from glitchygames.examples.brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from glitchygames.examples.clockwork_keep.game import ClockworkKeepScene
from glitchygames.game_objects import ball as ball_module
from glitchygames.scenes import SceneManager
from glitchygames.state import manager as save_manager_module
from glitchygames.tracing import StableSpriteIds, sample_scene_frame, write_trace

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from glitchygames.scenes import Scene

# Project root (scripts/ is one level below project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIRECTORY = PROJECT_ROOT / 'tests' / 'world' / 'golden'

FRAME_SECONDS = 1.0 / 60.0
DEFAULT_FRAME_COUNT = 900
RANDOM_SEED = 20261018
# The header's ``source`` field for traces this script records
GOLDEN_TRACE_SOURCE = 'golden-script'
SCREEN_RESOLUTION = '800x480'

# Where the fake clock starts: PaddleSlap derives its random.seed from perf_counter at init
FAKE_CLOCK_START_SECONDS = 1000.0

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

# Game key -> the game's scene class
GAME_SCENES: dict[str, type[Scene]] = {
    'clockwork_keep': ClockworkKeepScene,
    'brave_adventurer': BraveAdventurerScene,
    'brave_adventurer_papyrus': PapyrusBraveAdventurerScene,
    'paddleslap': paddleslap.Game,
}

# Where the Brave Adventurer script puts the player (world x on screen 2, ground level)
BRAVE_ADVENTURER_SKIP_TO_WORLD_X = 2400.0

# PaddleSlap paddle keys: (up key, down key) for the left and the right paddle
PADDLESLAP_PADDLE_KEYS: tuple[tuple[int, int], tuple[int, int]] = (
    (pygame.K_w, pygame.K_s),
    (pygame.K_UP, pygame.K_DOWN),
)
# A paddle holds still while the tracked ball's centre is within this many pixels of its own
PADDLESLAP_TRACKING_DEAD_ZONE_PIXELS = 12


class FakeClock:
    """A clock that advances only when told to, exactly one frame at a time."""

    def __init__(self, *, start_seconds: float) -> None:
        """Initialize the clock.

        Args:
            start_seconds: The time the clock reports before the first advance.

        """
        self.now_seconds = start_seconds

    def now(self) -> float:
        """Return the current fake time.

        Returns:
            The current time in seconds.

        """
        return self.now_seconds

    def advance(self, *, seconds: float) -> None:
        """Move the clock forward.

        Args:
            seconds: How far to advance.

        """
        self.now_seconds += seconds


def press(key: int) -> pygame.event.Event:
    """Build a key-down event.

    Args:
        key: The pygame key code.

    Returns:
        The KEYDOWN event.

    """
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=0)


def release(key: int) -> pygame.event.Event:
    """Build a key-up event.

    Args:
        key: The pygame key code.

    Returns:
        The KEYUP event.

    """
    return pygame.event.Event(pygame.KEYUP, key=key, mod=0, unicode='', scancode=0)


@dataclass
class InputScript:
    """Scripted input for one game.

    Attributes:
        key_events: Frame number -> key events posted before that frame runs.
        placements: Frame number -> callables that adjust the active scene before that frame
            runs (used to put the player somewhere a short script cannot walk to).
        per_frame: Optional callable run before every frame; it returns extra events to post
            (PaddleSlap's paddle tracking).

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


def _pause_and_resume(script: InputScript, *, pause_frame: int, resume_frame: int) -> None:
    """Pause with ESC and resume from the pause screen with SPACE.

    The ESC press and release go to the gameplay scene in the same frame; the pause scene
    resumes on the release of a SPACE press it saw.

    Args:
        script: The script to add to.
        pause_frame: The frame ESC is tapped before.
        resume_frame: The frame SPACE is tapped before.

    """
    script.at(pause_frame, press(pygame.K_ESCAPE), release(pygame.K_ESCAPE))
    script.at(resume_frame, press(pygame.K_SPACE))
    script.at(resume_frame + 2, release(pygame.K_SPACE))


def _stand_on_first_elevator(scene: Scene) -> None:
    """Put the Clockwork Keep player on the floor's first elevator, at rest.

    The elevator is at the top of the floor; reaching it takes more platforming than a
    900-frame script should hold, so the script places the player there.

    Args:
        scene: The active Clockwork Keep floor.

    """
    assert isinstance(scene, ClockworkKeepScene)
    elevator = scene.elevator_sprites[0]
    player = scene.player
    player.world_x = elevator.world_x + 5
    player.world_y = elevator.world_y - player.rect.height
    player.velocity_x = 0.0
    player.velocity_y = 0.0


def clockwork_keep_script() -> InputScript:
    """Clockwork Keep: walk right, jump, walk left, collect a cog, ride the elevator, pause.

    Returns:
        The input script.

    """
    script = InputScript()
    # Jump straight up at the spawn point: the first bronze cog hangs just above it
    script.tap(10, pygame.K_UP, held_frames=12)
    # Walk right (stopping well short of the right wall), with a jump that collects a cog
    script.at(70, press(pygame.K_RIGHT))
    script.tap(110, pygame.K_UP, held_frames=12)
    script.at(155, release(pygame.K_RIGHT))
    # Walk left from open floor (never turning against a wall)
    script.at(200, press(pygame.K_LEFT))
    script.tap(230, pygame.K_UP, held_frames=12)
    script.at(300, release(pygame.K_LEFT))
    # Ride the elevator to the next floor with the interact key (the ride lasts ~240 frames)
    script.place(330, _stand_on_first_elevator)
    script.tap(350, pygame.K_w, held_frames=4)
    # On the next floor: walk right, then pause and resume, then walk left
    script.at(640, press(pygame.K_RIGHT))
    script.tap(670, pygame.K_UP, held_frames=12)
    script.at(720, release(pygame.K_RIGHT))
    _pause_and_resume(script, pause_frame=740, resume_frame=790)
    script.at(820, press(pygame.K_LEFT))
    script.tap(840, pygame.K_UP, held_frames=12)
    script.at(880, release(pygame.K_LEFT))
    return script


def _place_before_screen_three(scene: Scene) -> None:
    """Put the Brave Adventurer player on the ground of screen 2, before the screen-3 walls.

    At 200 pixels per second a 900-frame run cannot reach the first pit (screen 4) from the
    spawn point, so the script skips ahead; the camera then catches up as it does in play.

    Args:
        scene: The active Brave Adventurer scene.

    """
    assert isinstance(scene, BraveAdventurerScene | PapyrusBraveAdventurerScene)
    scene.player.world_x = BRAVE_ADVENTURER_SKIP_TO_WORLD_X


def brave_adventurer_script() -> InputScript:
    """Brave Adventurer (both editions): run right collecting scarabs, pause, jump walls and a pit.

    Returns:
        The input script.

    """
    script = InputScript()
    # Screens 0 and 1: run right, jumping for the higher scarabs
    script.at(10, press(pygame.K_RIGHT))
    for jump_frame in (40, 120, 190, 260):
        script.tap(jump_frame, pygame.K_UP, held_frames=12)
    script.at(300, release(pygame.K_RIGHT))
    _pause_and_resume(script, pause_frame=320, resume_frame=370)
    # Skip ahead to screen 2, then jump the two screen-3 walls and the screen-4 pit
    script.place(400, _place_before_screen_three)
    script.at(410, press(pygame.K_RIGHT))
    for jump_frame in (460, 550, 742):
        script.tap(jump_frame, pygame.K_UP, held_frames=12)
    # Stop well before the screen-5 cobra, then walk back a little over open ground
    script.at(790, release(pygame.K_RIGHT))
    script.at(820, press(pygame.K_LEFT))
    script.at(860, release(pygame.K_LEFT))
    return script


class PaddleTracker:
    """Hold each PaddleSlap paddle's up or down key to follow the nearest approaching ball."""

    def __init__(self) -> None:
        """Initialize with no keys held."""
        self.held_keys: list[int | None] = [None, None]
        self.is_enabled = True

    def __call__(self, scene: Scene) -> list[pygame.event.Event]:
        """Return the key events that steer both paddles this frame.

        Args:
            scene: The active scene.

        Returns:
            Key releases and presses that change which keys are held.

        """
        if not isinstance(scene, paddleslap.Game) or not self.is_enabled:
            return []
        live_balls = [ball for ball in scene.balls if ball.alive()]
        paddles = (scene.player1, scene.player2)
        events: list[pygame.event.Event] = []
        for paddle_index, paddle in enumerate(paddles):
            # The left paddle tracks balls moving left, the right paddle balls moving right
            moving_toward = [
                ball for ball in live_balls if (ball.speed.x > 0) == (paddle_index == 1)
            ]
            wanted_key = None
            if moving_toward:
                target_ball = min(
                    moving_toward,
                    key=lambda ball: abs(ball.rect.centerx - paddle.rect.centerx),
                )
                up_key, down_key = PADDLESLAP_PADDLE_KEYS[paddle_index]
                offset = target_ball.rect.centery - paddle.rect.centery
                if offset < -PADDLESLAP_TRACKING_DEAD_ZONE_PIXELS:
                    wanted_key = up_key
                elif offset > PADDLESLAP_TRACKING_DEAD_ZONE_PIXELS:
                    wanted_key = down_key
            events.extend(self._hold(paddle_index=paddle_index, wanted_key=wanted_key))
        return events

    def release_all(self) -> list[pygame.event.Event]:
        """Release every held key and stop steering (before a pause).

        Returns:
            The key releases.

        """
        self.is_enabled = False
        events: list[pygame.event.Event] = []
        for paddle_index in range(len(self.held_keys)):
            events.extend(self._hold(paddle_index=paddle_index, wanted_key=None))
        return events

    def _hold(self, *, paddle_index: int, wanted_key: int | None) -> list[pygame.event.Event]:
        held_key = self.held_keys[paddle_index]
        if held_key == wanted_key:
            return []
        events: list[pygame.event.Event] = []
        if held_key is not None:
            events.append(release(held_key))
        if wanted_key is not None:
            events.append(press(wanted_key))
        self.held_keys[paddle_index] = wanted_key
        return events


def paddleslap_script() -> InputScript:
    """PaddleSlap: both paddles follow the nearest approaching ball; one pause and resume.

    Returns:
        The input script.

    """
    tracker = PaddleTracker()
    script = InputScript(per_frame=tracker)
    pause_frame = 450
    resume_frame = 510

    def release_paddle_keys(_scene: Scene) -> None:
        for event in tracker.release_all():
            pygame.event.post(event)

    def resume_tracking(_scene: Scene) -> None:
        tracker.is_enabled = True

    # PaddleSlap pauses on the release of SPACE; the pause scene resumes the same way
    script.place(pause_frame - 1, release_paddle_keys)
    script.at(pause_frame, press(pygame.K_SPACE), release(pygame.K_SPACE))
    script.at(resume_frame, press(pygame.K_SPACE))
    script.at(resume_frame + 2, release(pygame.K_SPACE))
    script.place(resume_frame + 4, resume_tracking)
    return script


SCRIPT_BUILDERS: dict[str, Callable[[], InputScript]] = {
    'clockwork_keep': clockwork_keep_script,
    'brave_adventurer': brave_adventurer_script,
    'brave_adventurer_papyrus': brave_adventurer_script,
    'paddleslap': paddleslap_script,
}


@contextlib.contextmanager
def _deterministic_environment(*, clock: FakeClock, save_root: Path) -> Generator[None]:
    """Replace every randomness and clock source the games read, then restore them.

    Args:
        clock: The fake clock PaddleSlap's time reads come from.
        save_root: Directory the games' save files go to.

    Yields:
        None, while the replacements are in place.

    """
    seeded_random = random.Random(RANDOM_SEED)

    def seeded_system_random() -> random.Random:
        return seeded_random

    def temporary_save_directory(app_name: str) -> Path:
        return save_root / app_name

    replacements: list[tuple[object, str, object]] = [
        (paddleslap, 'secrets', types.SimpleNamespace(randbelow=seeded_random.randrange)),
        (paddleslap, 'time', types.SimpleNamespace(time=clock.now, perf_counter=clock.now)),
        (ball_module, '_SERVE_RANDOM', seeded_random),
        (shake_module, 'secrets', types.SimpleNamespace(SystemRandom=seeded_system_random)),
        (save_manager_module, 'get_save_directory', temporary_save_directory),
    ]
    originals = [(owner, name, getattr(owner, name)) for owner, name, _ in replacements]
    random_state = random.getstate()
    try:
        for owner, name, replacement in replacements:
            setattr(owner, name, replacement)
        yield
    finally:
        for owner, name, original in originals:
            setattr(owner, name, original)
        # PaddleSlap reseeds the global random module from its (fake) clock
        random.setstate(random_state)


@contextlib.contextmanager
def _command_line(arguments: list[str]) -> Generator[None]:
    """Temporarily replace sys.argv (GameEngine parses it at construction).

    Args:
        arguments: The arguments after the program name.

    Yields:
        None, while sys.argv holds the arguments.

    """
    original_arguments = sys.argv
    sys.argv = ['record_golden_traces', *arguments]
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
        SceneManager._instance = manager
        return manager

    @classmethod
    def uninstall(cls) -> None:
        """Clear the singleton so the next game starts from a fresh scene manager."""
        SceneManager._reset()
        cls._reset()

    def run_frame(self) -> None:
        """Run one frame the way SceneManager.start() does, without pacing or timing."""
        # The transition branch mirrors SceneManager.start()
        if self._active_transition is not None:
            transition_done = self._active_transition.update(self.dt)
            self._update_frame_services()
            self._active_transition.render(self.screen)
            self._present_frame(full_update=True)
            if transition_done:
                self._finalize_transition()
        else:
            self._run_scene_frame()


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


def _start_game(game_key: str) -> GoldenTraceSceneManager:
    """Construct the game engine and install the game's scene.

    Args:
        game_key: Which game to start.

    Returns:
        The scene manager with the game scene active.

    """
    scene_class = GAME_SCENES[game_key]
    manager = GoldenTraceSceneManager.install()
    with _command_line([
        '--windowed',
        '--resolution',
        SCREEN_RESOLUTION,
        '--log-level',
        'warning',
        '--input-mode',
        'joystick',
    ]):
        engine = GoldenTraceEngine(game=scene_class)
    assert engine.scene_manager is manager
    engine.install_game(scene_class=scene_class)
    return manager


def _discard_environment_events() -> None:
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


def record_trace(game_key: str, *, frame_count: int) -> dict[str, Any]:
    """Run a game headless with its scripted input and record every sprite each frame.

    Args:
        game_key: Which game (a key of GAME_SCENES).
        frame_count: How many frames to run.

    Returns:
        The trace: game key, frame seconds and one record per frame.

    """
    script = SCRIPT_BUILDERS[game_key]()
    clock = FakeClock(start_seconds=FAKE_CLOCK_START_SECONDS)
    frames: list[dict[str, Any]] = []
    sprite_ids = StableSpriteIds()
    with (
        tempfile.TemporaryDirectory(prefix='golden-trace-saves-') as save_directory,
        _deterministic_environment(clock=clock, save_root=Path(save_directory)),
    ):
        manager = _start_game(game_key)
        try:
            for frame_number in range(frame_count):
                clock.advance(seconds=FRAME_SECONDS)
                manager.dt = FRAME_SECONDS
                _discard_environment_events()
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
        finally:
            pygame.event.clear()
            GoldenTraceSceneManager.uninstall()
    return {'game': game_key, 'frame_seconds': FRAME_SECONDS, 'frames': frames}


def golden_path(game_key: str) -> Path:
    """Return where a game's golden trace is stored.

    Args:
        game_key: Which game.

    Returns:
        The trace file path (gzip-compressed JSON Lines, see glitchygames/tracing.py).

    """
    return GOLDEN_DIRECTORY / f'{game_key}.jsonl.gz'


def main() -> None:
    """Record and write the golden trace of every game."""
    for game_key in GAME_SCENES:
        trace = record_trace(game_key, frame_count=DEFAULT_FRAME_COUNT)
        path = golden_path(game_key)
        write_trace({'source': GOLDEN_TRACE_SOURCE, **trace}, path=path)
        sys.stdout.write(f'{game_key}: {len(trace["frames"])} frames -> {path}\n')


if __name__ == '__main__':
    main()
