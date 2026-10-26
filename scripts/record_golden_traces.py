"""Record golden traces of the example games, driven headless with scripted input.

A golden trace is the rect and visibility of every sprite in the active scene's
``all_sprites``, recorded after each frame of a scripted, fully deterministic run. The
traces in ``tests/world/golden/`` were recorded before the engine world-space change
(plans/2026-10-18-engine-world-space.md); ``tests/world/test_golden_traces.py`` replays the
same scripts and fails on any difference that is not listed and justified there. Only the games
in ``GOLDEN_TRACE_GAMES`` have one; every game in ``GAME_SCENES`` has a golden input script
(``SCRIPT_BUILDERS``), which scripts/record_scripted_session.py records as its golden replay.

Determinism:
    - Every frame runs with ``dt`` fixed at 1/60 second.
    - Every game is started with ``--random-seed RANDOM_SEED``: all the randomness the games
      use (serves, PaddleSlap's spawn positions and colours, shakes) comes from the engine's
      named streams (``glitchygames/randomness.py``), so the seed fixes it. Nothing is patched.
    - PaddleSlap's ball spawn cooldown reads ``Scene.game_time``, which the fixed dt drives
      (exactly 1/60 second per unpaused frame), so no clock is patched.
    - Save files go to a fresh temporary directory, so high scores on disk cannot leak in.
    - Events the host environment posts (window focus, window shown, audio devices, ...) are
      discarded before each frame. SDL's dummy video driver posts a focus-lost event at
      startup, which would auto-pause Clockwork Keep.

Ids: each sprite gets ``<ClassName>#<n>`` the first time it is seen, where n counts that
class's sprites in order of first appearance over the whole run. Ids never renumber when a
sprite is removed (a collected coin, a dead ball).

Scope and maintenance:
    - ``GoldenTraceSceneManager.run_frame`` runs ``SceneManager._run_frame``, the same frame
      body ``SceneManager.start()`` runs (both branches, and the ``--record-trace`` hook).
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
import math
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, Unpack, override

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

import paddleslap
from brave_adventurer.game import BraveAdventurerScene
from brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from clockwork_keep.game import ClockworkKeepScene
from glitchygames.engine import GameEngine
from glitchygames.events import AUDIO_EVENTS, WINDOW_EVENTS
from glitchygames.examples.drawing_fire.game import DrawingFireScene
from glitchygames.examples.drawing_fire.seats import LEAVE_HOLD_SECONDS, Stage
from glitchygames.scenes import SceneManager
from glitchygames.state import manager as save_manager_module
from glitchygames.testing.keys import qwerty_scancode
from glitchygames.tracing import StableSpriteIds, sample_scene_frame, write_trace
from mr_muncher.autopilot import Autopilot
from mr_muncher.game import MrMuncherScene
from mr_muncher.maze import Direction

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from glitchygames.replay import ReplayResult
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

# Game key -> the game's scene class, for every game with a golden input script
GAME_SCENES: dict[str, type[Scene]] = {
    'clockwork_keep': ClockworkKeepScene,
    'brave_adventurer': BraveAdventurerScene,
    'brave_adventurer_papyrus': PapyrusBraveAdventurerScene,
    'paddleslap': paddleslap.Game,
    'mr_muncher': MrMuncherScene,
    'drawing_fire': DrawingFireScene,
}

# Game key -> the module holding its main() (where its console script's entry point is, for a
# game in the engine's examples): a game moved into its own package names its package
# (plans/2026-10-24-workspace-packages.md). A member's console script may be a launcher instead
# (Brave Adventurer's, brave_adventurer_modes, starts both its games; scripts/
# record_scripted_session.py GAME_CONSOLE_SCRIPTS)
GAME_MODULES: dict[str, str] = {
    'clockwork_keep': 'clockwork_keep',
    'brave_adventurer': 'brave_adventurer',
    'brave_adventurer_papyrus': 'brave_adventurer_papyrus',
    'paddleslap': 'paddleslap',
    'mr_muncher': 'mr_muncher',
    'drawing_fire': 'glitchygames.examples.drawing_fire',
}

# The games whose golden traces (tests/world/golden/) were recorded before the world-space
# change: tests/world/test_golden_traces.py compares these. Games written after it (Mr. Muncher,
# Drawing Fire) have no such baseline; their golden replays cover them (Mr. Muncher's in its
# package, src/games/mr-muncher/tests/fixtures/replays/; Drawing Fire's in tests/fixtures/replays/).
GOLDEN_TRACE_GAMES: tuple[str, ...] = (
    'clockwork_keep',
    'brave_adventurer',
    'brave_adventurer_papyrus',
    'paddleslap',
)

# Where the Brave Adventurer script puts the player (world x on screen 2, ground level)
BRAVE_ADVENTURER_SKIP_TO_WORLD_X = 2400.0

# Mr. Muncher: the arrow key for each direction; the autopilot presses a key again if the player
# still wants another way this many frames after it was pressed; it walks into a muncher (once)
# after this much of the level's game time; the script pauses and resumes on these frames
MR_MUNCHER_DIRECTION_KEYS: dict[Direction, int] = {
    Direction.UP: pygame.K_UP,
    Direction.LEFT: pygame.K_LEFT,
    Direction.DOWN: pygame.K_DOWN,
    Direction.RIGHT: pygame.K_RIGHT,
}
MR_MUNCHER_REPRESS_FRAMES = 4
MR_MUNCHER_SEEK_CAPTURE_SECONDS = 22.0
MR_MUNCHER_PAUSE_FRAME = 600
MR_MUNCHER_RESUME_FRAME = 660

# Drawing Fire: the keyboard player's seat name (the first seat opened); the frames before
# which the left mouse button goes down (True) or up (False); the frame the script starts
# holding Escape (after the player's first death) and how many frames longer than the seats'
# LEAVE_HOLD_SECONDS (counted in frames of FRAME_SECONDS) it holds it, so a little over a second
DRAWING_FIRE_PLAYER_NAME = 'P1'
DRAWING_FIRE_FIRE_BUTTON_CHANGES: dict[int, bool] = {150: True, 380: False, 400: True, 600: False}
DRAWING_FIRE_LEAVE_FRAME = 1500
DRAWING_FIRE_LEAVE_SPARE_FRAMES = 10
DRAWING_FIRE_LEAVE_HOLD_FRAMES = (
    math.ceil(LEAVE_HOLD_SECONDS / FRAME_SECONDS) + DRAWING_FIRE_LEAVE_SPARE_FRAMES
)
# The mouse follows its target only once the target's chest is more than this many pixels from
# it, as a hand on a mouse does (and so a walking target is not a motion every frame)
DRAWING_FIRE_AIM_SLACK_PIXELS = 8
# pygame's mouse button number for the left button (MOUSEBUTTONDOWN's ``button``)
LEFT_MOUSE_BUTTON = 1

# PaddleSlap paddle keys: (up key, down key) for the left and the right paddle
PADDLESLAP_PADDLE_KEYS: tuple[tuple[int, int], tuple[int, int]] = (
    (pygame.K_w, pygame.K_s),
    (pygame.K_UP, pygame.K_DOWN),
)
# A paddle holds still while the tracked ball's centre is within this many pixels of its own
PADDLESLAP_TRACKING_DEAD_ZONE_PIXELS = 12


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


def stand_on_first_elevator(scene: Scene) -> None:
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
    script.place(330, stand_on_first_elevator)
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
            # Balls are world sprites: their rect is written by the engine during the frame
            # (before the first frame it is the constructor's placeholder). drawn_center() is
            # the snapped world position, what the ball's setters kept in rect when the
            # baseline was recorded, so the tracker steers exactly as it did then.
            if moving_toward:
                target_ball = min(
                    moving_toward,
                    key=lambda ball: abs(ball.drawn_center()[0] - paddle.rect.centerx),
                )
                up_key, down_key = PADDLESLAP_PADDLE_KEYS[paddle_index]
                offset = target_ball.drawn_center()[1] - paddle.rect.centery
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


class MuncherSteering:
    """Hold the arrow key for the way Mr. Muncher's autopilot asks for, frame by frame.

    The autopilot (src/games/mr-muncher/mr_muncher/autopilot.py) reads the scene and names a
    direction; this presses that direction's arrow key (releasing the one held before). A key
    is pressed again when the player still wants another way after MR_MUNCHER_REPRESS_FRAMES
    (a new life starts heading left, whatever key is held). Nothing is pressed while another
    scene (the pause screen) is active.
    """

    def __init__(self, *, seek_capture_after_seconds: float | None) -> None:
        """Steer with an autopilot.

        Args:
            seek_capture_after_seconds: When the autopilot walks into a muncher (once), in
                seconds of the level's game time; None never.

        """
        self.autopilot = Autopilot(seek_capture_after_seconds=seek_capture_after_seconds)
        self.held_key: int | None = None
        self.frames_held = 0
        self.key_to_press: int | None = None

    def __call__(self, scene: Scene) -> list[pygame.event.Event]:
        """Return the key events that steer the player this frame.

        Args:
            scene: The active scene.

        Returns:
            Key releases and presses.

        """
        if not isinstance(scene, MrMuncherScene):
            return []
        self.frames_held += 1
        if self.key_to_press is not None:
            key, self.key_to_press = self.key_to_press, None
            return self._hold(key)
        direction = self.autopilot.choose_direction(scene=scene)
        if direction is None:
            return []
        key = MR_MUNCHER_DIRECTION_KEYS[direction]
        if key != self.held_key:
            return self._hold(key)
        if (
            scene.player.wanted_direction is not direction
            and self.frames_held >= MR_MUNCHER_REPRESS_FRAMES
        ):
            # Release now and press again next frame: a press in the same frame as its
            # release would not count as a new press
            self.key_to_press = key
            return self._hold(None)
        return []

    def _hold(self, key: int | None) -> list[pygame.event.Event]:
        """Release the held key (if any) and press another (if any).

        Args:
            key: The key to hold, or None to hold none.

        Returns:
            The release and press events.

        """
        events: list[pygame.event.Event] = []
        if self.held_key is not None:
            events.append(release(self.held_key))
        if key is not None:
            events.append(press(key))
        self.held_key = key
        self.frames_held = 0
        return events


def mr_muncher_script() -> InputScript:
    """Mr. Muncher: the autopilot plays, loses a life on purpose, and the game pauses once.

    The autopilot eats sprockets, a snack and frightened munchers; after
    MR_MUNCHER_SEEK_CAPTURE_SECONDS it walks into a muncher, so the session holds a death and
    the next life's READY.

    Returns:
        The input script.

    """
    steering = MuncherSteering(seek_capture_after_seconds=MR_MUNCHER_SEEK_CAPTURE_SECONDS)
    script = InputScript(per_frame=steering)
    _pause_and_resume(
        script, pause_frame=MR_MUNCHER_PAUSE_FRAME, resume_frame=MR_MUNCHER_RESUME_FRAME
    )
    return script


class DrawingFireMouse:
    """The keyboard player's mouse: it aims at the nearest enemy and presses the fire button.

    Drawing Fire's keyboard player aims at the mouse and fires with its left button
    (glitchygames/examples/drawing_fire/players.py). While the player drives a soldier, the
    mouse moves onto the chest of the living enemy nearest him whenever that chest is more than
    DRAWING_FIRE_AIM_SLACK_PIXELS away, as a player tracking a target would (no motion while he
    is not playing). The left button goes down or up before each frame ``button_changes``
    names, where the mouse is.

    A per-frame input of an InputScript is called once per frame from the supervisor slot of
    frame 0 on, each call posting input for the next frame (record_scripted_session.py), so the
    first call is for frame 1 and each later call for the frame after.
    """

    def __init__(self, *, button_changes: dict[int, bool]) -> None:
        """Start with the mouse unmoved and its buttons up.

        Args:
            button_changes: Frame number -> the left button goes down (True) or up (False)
                before that frame.

        """
        self.button_changes = button_changes
        # The frame the next call posts input for
        self.next_frame = 1
        self.mouse_position = (0, 0)
        self.is_button_down = False

    def __call__(self, scene: Scene) -> list[pygame.event.Event]:
        """Return this frame's mouse motion and button change, if any.

        Args:
            scene: The active scene.

        Returns:
            A MOUSEMOTION, a MOUSEBUTTONDOWN or MOUSEBUTTONUP, both or neither.

        """
        frame_number = self.next_frame
        self.next_frame += 1
        events: list[pygame.event.Event] = []
        target_position = self._target_position(scene)
        if (
            target_position is not None
            and math.dist(target_position, self.mouse_position) > DRAWING_FIRE_AIM_SLACK_PIXELS
        ):
            previous_x, previous_y = self.mouse_position
            self.mouse_position = target_position
            events.append(
                pygame.event.Event(
                    pygame.MOUSEMOTION,
                    pos=target_position,
                    rel=(target_position[0] - previous_x, target_position[1] - previous_y),
                    buttons=(int(self.is_button_down), 0, 0),
                    touch=False,
                )
            )
        if frame_number in self.button_changes:
            self.is_button_down = self.button_changes[frame_number]
            events.append(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN if self.is_button_down else pygame.MOUSEBUTTONUP,
                    pos=self.mouse_position,
                    button=LEFT_MOUSE_BUTTON,
                    touch=False,
                )
            )
        return events

    @staticmethod
    def _target_position(scene: Scene) -> tuple[int, int] | None:
        """Find the chest of the living enemy nearest the player's soldier (ties: lower id).

        Returns:
            The position in window pixels, or None while the player drives no soldier or no
            enemy stands.

        """
        if not isinstance(scene, DrawingFireScene):
            return None
        seat = scene.seats.players.get(DRAWING_FIRE_PLAYER_NAME)
        if seat is None or seat.stage is not Stage.PLAYING or seat.soldier_id is None:
            return None
        soldier = scene.battle.soldier(seat.soldier_id)
        enemies = scene.battle.living(soldier.side.opponent)
        if not enemies:
            return None
        target = min(enemies, key=lambda enemy: (abs(enemy.x - soldier.x), enemy.soldier_id))
        target_x, target_y = target.chest
        return (round(target_x), round(target_y))


def drawing_fire_script() -> InputScript:
    """Drawing Fire: the keyboard player joins, fights, dies, fights on and leaves.

    Enter opens a seat; RIGHT moves the side card from Random to the Pencil Platoon and Enter
    confirms it; D and A move the soldier highlight right and back, and keypad Enter takes the
    highlighted soldier. The player then fires (the left mouse button, held, let go and held
    again; DrawingFireMouse aims at the nearest enemy), walks right toward the fight (D), steps
    back (the left arrow, then A) and walks on (the right arrow), letting go of fire on the way,
    through the Graphite Brigade's line, where he stands until he is shot down and takes over
    another Platoon soldier. Then he holds Escape until he leaves. Every keyboard and mouse
    control the game reads is used here; Q, which quits on its release, is the controls tail's
    (record_scripted_session.py). Escape's release never quits: Drawing Fire's scene ignores it.

    Returns:
        The input script.

    """
    script = InputScript(
        per_frame=DrawingFireMouse(button_changes=DRAWING_FIRE_FIRE_BUTTON_CHANGES)
    )
    # Join, choose the Pencil Platoon, step the highlight right and back, take the soldier
    script.tap(30, pygame.K_RETURN, held_frames=4)
    script.tap(50, pygame.K_RIGHT, held_frames=4)
    script.tap(70, pygame.K_RETURN, held_frames=4)
    script.tap(90, pygame.K_d, held_frames=4)
    script.tap(110, pygame.K_a, held_frames=4)
    script.tap(130, pygame.K_KP_ENTER, held_frames=4)
    # Fight: walk right toward the Brigade, step back, then walk on through its line and stand
    # there, ahead of his own side, the soldier nearest its pistols, until shot down (about frame
    # 740 to 920; fire is let go on the way in, at frame 600, so the Brigade keeps its pistols)
    script.tap(160, pygame.K_d, held_frames=200)
    script.tap(420, pygame.K_LEFT, held_frames=40)
    script.tap(470, pygame.K_a, held_frames=40)
    script.tap(520, pygame.K_RIGHT, held_frames=340)
    # Hold Escape until the seat is left
    script.tap(
        DRAWING_FIRE_LEAVE_FRAME,
        pygame.K_ESCAPE,
        held_frames=DRAWING_FIRE_LEAVE_HOLD_FRAMES,
    )
    return script


SCRIPT_BUILDERS: dict[str, Callable[[], InputScript]] = {
    'clockwork_keep': clockwork_keep_script,
    'brave_adventurer': brave_adventurer_script,
    'brave_adventurer_papyrus': brave_adventurer_script,
    'paddleslap': paddleslap_script,
    'mr_muncher': mr_muncher_script,
    'drawing_fire': drawing_fire_script,
}


@contextlib.contextmanager
def deterministic_environment(*, save_root: Path) -> Generator[None]:
    """Replace the save directory, then restore it.

    Randomness needs no replacement: ``_start_game`` passes ``--random-seed``. Clocks need
    none either: PaddleSlap's cooldown now uses Scene.game_time, which the harness's fixed dt
    drives.

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
    game_key: str, *, random_seed: int, extra_arguments: list[str] | None = None
) -> GoldenTraceSceneManager:
    """Construct the game engine and install the game's scene.

    Args:
        game_key: Which game to start.
        random_seed: The run's master seed (``--random-seed``).
        extra_arguments: More command-line arguments (``--replay-trace PATH``).

    Returns:
        The scene manager with the game scene active.

    """
    scene_class = GAME_SCENES[game_key]
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
def _golden_game(
    game_key: str, *, random_seed: int, extra_arguments: list[str] | None = None
) -> Generator[GoldenTraceSceneManager]:
    """Start a game in the harness with temporary saves; tear it all down afterwards.

    Args:
        game_key: Which game (a key of GAME_SCENES).
        random_seed: The run's master seed (``--random-seed``).
        extra_arguments: More command-line arguments (``--replay-trace PATH``).

    Yields:
        The scene manager with the game scene active.

    """
    with (
        tempfile.TemporaryDirectory(prefix='golden-trace-saves-') as save_directory,
        deterministic_environment(save_root=Path(save_directory)),
    ):
        manager = _start_game(game_key, random_seed=random_seed, extra_arguments=extra_arguments)
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
    game_key: str,
    *,
    frame_count: int,
    recording_path: Path | None = None,
    random_seed: int = RANDOM_SEED,
    **hooks: Unpack[RecordTraceHooks],
) -> dict[str, Any]:
    """Run a game headless with its scripted input and record every sprite each frame.

    Args:
        game_key: Which game (a key of GAME_SCENES).
        frame_count: How many frames to run.
        recording_path: If given, the engine also records the run there as ``--record-trace``
            would (GameEngine.start_trace_recording), for checking recordings against the
            harness's own frames.
        random_seed: The run's master seed, passed as ``--random-seed``.
        **hooks: Optional callbacks into the run, by keyword (``RecordTraceHooks``).

    Returns:
        The trace: game key, frame seconds and one record per frame.

    """
    frame_observer = hooks.get('frame_observer')
    before_recording = hooks.get('before_recording')
    script = SCRIPT_BUILDERS[game_key]()
    frames: list[dict[str, Any]] = []
    sprite_ids = StableSpriteIds()
    with _golden_game(game_key, random_seed=random_seed) as manager:
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
    return {'game': game_key, 'frame_seconds': FRAME_SECONDS, 'frames': frames}


def replay_golden_recording(
    *, game_key: str, path: Path, frame_limit: int | None = None
) -> ReplayResult:
    """Replay a recording made by record_trace(recording_path=...) through the harness.

    Key events and per-frame input come from the recording (the replay's event pump), so they
    are not posted again. The script's placements are not input: they move sprites directly,
    like a supervisor, so they are applied again on the same frames, before the frame runs, as
    record_trace applies them. (A placement that posts events, such as PaddleSlap's key
    release before its pause, posts real events the replay drops: the recording serves them.)

    The result is settled as GameEngine._shutdown settles it (``finish_run``): a harness that
    stops before the recording's last frame reports a length divergence.

    Args:
        game_key: Which game (a key of GAME_SCENES).
        path: The recording.
        frame_limit: Stop after this many frames even if the replay goes on (None: run until
            the replay stops).

    Returns:
        The replay's result.

    """
    script = SCRIPT_BUILDERS[game_key]()
    # Headless: a watched replay would pause at its end (or divergence) instead of stopping
    with _golden_game(
        game_key,
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


def golden_path(game_key: str) -> Path:
    """Return where a game's golden trace is stored.

    Args:
        game_key: Which game.

    Returns:
        The trace file path (gzip-compressed JSON Lines, see glitchygames/tracing.py).

    """
    return GOLDEN_DIRECTORY / f'{game_key}.jsonl.gz'


def main() -> None:
    """Record and write the golden trace of every game that has one (GOLDEN_TRACE_GAMES)."""
    for game_key in GOLDEN_TRACE_GAMES:
        trace = record_trace(game_key, frame_count=DEFAULT_FRAME_COUNT)
        path = golden_path(game_key)
        write_trace(trace={'source': GOLDEN_TRACE_SOURCE, **trace}, path=path)
        sys.stdout.write(f'{game_key}: {len(trace["frames"])} frames -> {path}\n')


if __name__ == '__main__':
    main()
