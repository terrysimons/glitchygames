"""Our games' golden input scripts: what the scripted player of each of our games presses.

Each builder takes no arguments and returns a fresh ``InputScript``
(glitchygames/replay/tools/golden_traces.py), so each is a ``MODULE:NAME`` target for the
engine's tools (``--input-script scripts.golden_inputs:paddleslap_script``, run from the
repository root; ``load_input_script``). scripts/record_golden_traces.py names each game's
builder (``SCRIPT_BUILDERS``) for its golden trace, and scripts/record_scripted_session.py for
its golden replay. Each game's controls tail (``*_controls``), which its golden replay plays
after the script (``--controls-tail scripts.golden_inputs:paddleslap_controls``), is here too.
They are this repository's test data, not engine code.

Games are loaded only when needed: each script imports what it reads of its game where it reads
it, so importing this module imports no workspace member.

Moved from scripts/record_golden_traces.py (Stage D, Task D4a), unchanged; the controls tails
from scripts/record_scripted_session.py (Task D4b), unchanged.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from glitchygames.replay.tools.golden_traces import FRAME_SECONDS, InputScript, press, release

if TYPE_CHECKING:
    from glitchygames.scenes import Scene

# Where the Brave Adventurer script puts the player (world x on screen 2, ground level)
BRAVE_ADVENTURER_SKIP_TO_WORLD_X = 2400.0

# Mr. Muncher: the arrow key for each direction (by the name of its mr_muncher.maze.Direction
# member, so this script imports no game); the autopilot presses a key again if the player
# still wants another way this many frames after it was pressed; it walks into a muncher (once)
# after this much of the level's game time; the script pauses and resumes on these frames
MR_MUNCHER_DIRECTION_KEYS: dict[str, int] = {
    'UP': pygame.K_UP,
    'LEFT': pygame.K_LEFT,
    'DOWN': pygame.K_DOWN,
    'RIGHT': pygame.K_RIGHT,
}
MR_MUNCHER_REPRESS_FRAMES = 4
MR_MUNCHER_SEEK_CAPTURE_SECONDS = 22.0
MR_MUNCHER_PAUSE_FRAME = 600
MR_MUNCHER_RESUME_FRAME = 660

# Drawing Fire: the keyboard player's seat name (the first seat opened); the frames before
# which the left mouse button goes down (True) or up (False); the frame the script starts
# holding Escape (after the player's first death) and how many frames longer than the seats'
# LEAVE_HOLD_SECONDS (counted in frames of FRAME_SECONDS) it holds it, so a little over a second,
# as drawing_fire_leave_hold_frames counts it
DRAWING_FIRE_PLAYER_NAME = 'P1'
DRAWING_FIRE_FIRE_BUTTON_CHANGES: dict[int, bool] = {150: True, 380: False, 400: True, 600: False}
DRAWING_FIRE_LEAVE_FRAME = 1500
DRAWING_FIRE_LEAVE_SPARE_FRAMES = 10
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
# A paddle holds still while the tracked ball's center is within this many pixels of its own
PADDLESLAP_TRACKING_DEAD_ZONE_PIXELS = 12


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
    from clockwork_keep.game import ClockworkKeepScene

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
    from brave_adventurer.game import BraveAdventurerScene
    from brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene

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
        from paddleslap import Game as PaddleSlapGame

        if not isinstance(scene, PaddleSlapGame) or not self.is_enabled:
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

    The autopilot (src/games/mr-muncher/src/mr_muncher/autopilot.py) reads the scene and names a
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
        from mr_muncher.autopilot import Autopilot

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
        from mr_muncher.game import MrMuncherScene

        if not isinstance(scene, MrMuncherScene):
            return []
        self.frames_held += 1
        if self.key_to_press is not None:
            key, self.key_to_press = self.key_to_press, None
            return self._hold(key)
        direction = self.autopilot.choose_direction(scene=scene)
        if direction is None:
            return []
        key = MR_MUNCHER_DIRECTION_KEYS[direction.name]
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
    (src/games/drawing-fire/src/drawing_fire/players.py). While the player drives a soldier, the
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
        from drawing_fire.game import DrawingFireScene
        from drawing_fire.seats import Stage

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


def drawing_fire_leave_hold_frames() -> int:
    """Return how many frames Drawing Fire's script holds Escape to leave its seat.

    The seats' LEAVE_HOLD_SECONDS, counted in frames of FRAME_SECONDS, and
    DRAWING_FIRE_LEAVE_SPARE_FRAMES more.

    Returns:
        The frames.

    """
    from drawing_fire.seats import LEAVE_HOLD_SECONDS

    return math.ceil(LEAVE_HOLD_SECONDS / FRAME_SECONDS) + DRAWING_FIRE_LEAVE_SPARE_FRAMES


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
        held_frames=drawing_fire_leave_hold_frames(),
    )
    return script


# The controls tails: input a golden replay session plays after the golden script's frames
# (scripts/record_scripted_session.py CONTROLS_TAIL_BUILDERS; never part of a script, so the golden
# traces never see them). Moved from scripts/record_scripted_session.py (Stage D, Task D4b),
# unchanged.


def _pause_with(tail: InputScript, *, key: int, pause_frame: int, resume_frame: int) -> None:
    """Pause with a key, then resume from the engine's pause screen with SPACE.

    Args:
        tail: The controls tail to add to.
        key: The game's pause key (tapped within one frame, as the golden scripts do).
        pause_frame: The tail frame the pause key is tapped before.
        resume_frame: The tail frame SPACE is pressed before (released two frames later).

    """
    tail.at(pause_frame, press(key), release(key))
    tail.at(resume_frame, press(pygame.K_SPACE))
    tail.at(resume_frame + 2, release(pygame.K_SPACE))


def clockwork_keep_controls() -> InputScript:
    """Clockwork Keep: run right (left shift), jump with SPACE, interact, pause, quit with Q.

    Returns:
        The controls tail (frames count from the tail's first frame).

    """
    tail = InputScript()
    tail.at(10, press(pygame.K_LSHIFT))
    tail.at(12, press(pygame.K_RIGHT))
    tail.at(40, release(pygame.K_RIGHT))
    tail.at(42, release(pygame.K_LSHIFT))
    tail.tap(60, pygame.K_SPACE, held_frames=12)
    # Interact away from an elevator: the press is read, nothing rides
    tail.tap(90, pygame.K_w, held_frames=4)
    _pause_with(tail, key=pygame.K_ESCAPE, pause_frame=110, resume_frame=160)
    tail.at(200, press(pygame.K_q))
    return tail


def brave_adventurer_controls() -> InputScript:
    """Brave Adventurer (both editions): walk left, jump with SPACE, quit with Q.

    The golden script already pauses (ESC) and resumes, inside the recorded frames.

    Returns:
        The controls tail (frames count from the tail's first frame).

    """
    tail = InputScript()
    tail.at(10, press(pygame.K_LEFT))
    tail.tap(20, pygame.K_SPACE, held_frames=12)
    tail.at(50, release(pygame.K_LEFT))
    tail.at(70, press(pygame.K_q))
    return tail


def paddleslap_controls() -> InputScript:
    """PaddleSlap: quit with both of the base scene's quit keys, Q and ESC, released together.

    PaddleSlap binds no quit of its own: the engine's Scene quits on the release of Q or ESC
    (each release posts a QUIT), so the recording holds two internal QUITs and a replay in which
    either key no longer quits diverges.

    Returns:
        The controls tail (frames count from the tail's first frame).

    """
    tail = InputScript()
    tail.at(10, press(pygame.K_q))
    tail.at(12, press(pygame.K_ESCAPE))
    tail.at(20, release(pygame.K_q), release(pygame.K_ESCAPE))
    return tail


def mr_muncher_controls() -> InputScript:
    """Mr. Muncher: steer with WASD (the autopilot uses the arrows), pause with P, quit with Q.

    The golden script already pauses with ESC and resumes. The tail is short: the fixture must
    stay under 100 KB.

    Returns:
        The controls tail (frames count from the tail's first frame).

    """
    tail = InputScript()
    for tap_frame, key in ((5, pygame.K_w), (20, pygame.K_a), (35, pygame.K_s), (50, pygame.K_d)):
        tail.tap(tap_frame, key, held_frames=10)
    _pause_with(tail, key=pygame.K_p, pause_frame=65, resume_frame=95)
    tail.at(120, press(pygame.K_q))
    return tail


def drawing_fire_controls() -> InputScript:
    """Drawing Fire: quit with Q (the base scene quits on its release).

    The golden script already uses every control the game reads, the left mouse button and the
    mouse included. Drawing Fire has no pause (tests/replay/test_golden_replays.py
    GAMES_WITHOUT_A_PAUSE), and Escape is the keyboard's Back, never a quit.

    Returns:
        The controls tail (frames count from the tail's first frame).

    """
    tail = InputScript()
    tail.at(10, press(pygame.K_q))
    tail.at(12, release(pygame.K_q))
    return tail
