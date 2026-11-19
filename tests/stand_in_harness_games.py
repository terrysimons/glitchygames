"""Stand-ins for the games the golden-trace harness runs.

The harness's ``record_trace`` and ``replay_golden_recording``
(glitchygames/replay/tools/golden_traces.py), the scripted-session recorder's
``record_scripted_session`` (glitchygames/replay/tools/scripted_sessions.py) and the tests'
``replay_through_engine`` (tests/replay/replay_helpers.py) take a scene class and an input
script, so an engine test passes a stand-in's directly: the engine's tests import no game, run
no game's code and import nothing from ``scripts`` (this module imports only the engine).

``TowerFloorScene`` stands in for Clockwork Keep's golden script: a 900-frame session with key
taps on known frames, an elevator ride (the engine's ``ElevatorTransition``) and a pause through
the engine's ``PauseScene``.

``SteeredPaddleScene`` stands in for PaddleSlap's rally in a short scripted session: a paddle
steered by key events (``steered_paddle_script``). Its facts: it reads key events (so the
session records external key events) and polls no input (it needs no
``polled_input``); its script places no sprite; the paddle is a sprite on every frame; it
moves a fixed step per frame, so a replay is deterministic; it posts no event of its own; its
only controls are the arrows, and the base scene's quit keys (Q, ESC) end it (``pygame.K_x``
does nothing).

``SoundingRallyScene`` stands in for a game that uses the sound library: what it reads of the
audio engine is put into its sprites, so a replay compares it. Its facts: it asks for its two
sounds in ``setup()`` (``Instrument`` sounds: no sound directory); ``length_probe`` sits at
``x`` = its blip's length in milliseconds and ``y`` = its peak in hundredths; ``playing_probe``
moves right while its long note (``LONG_NOTE_SECONDS``, played on ``LONG_NOTE_FRAME``) plays;
on ``BURST_FRAME`` it plays ``BURST_PLAYS`` blips, more than the effects bus has channels, so
the long note and some blips are stolen; ``burst_probe`` sits at ``x`` = how many of the burst's
handles still play and ``y`` = the steals so far. It takes no input, and ends the run itself
after ``SOUNDING_RALLY_FRAMES`` frames (``SceneManager.quit``: no event).

``PadReadoutScene`` stands in for a game read from a joystick: its marker's x follows the
stand-in stick's polled axis 0, so a recorded session with the stand-in pad replays what the
pad did (``PadReadoutScene``'s docstring has its facts).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.audio import Instrument
from glitchygames.input.state import current_input
from glitchygames.replay.tools.golden_traces import InputScript, press, release
from glitchygames.scenes import Scene
from glitchygames.transitions.elevator import ElevatorTransition
from tests.input.stand_in_devices import STAND_IN_STICK

if TYPE_CHECKING:
    from glitchygames.events.base import KeyEvent

# The tower session's frames and key frames, copied from Clockwork Keep's golden script
# (scripts/golden_inputs.py, clockwork_keep_script, and the 900 frames the
# recording test ran it for, its former CLOCKWORK_KEEP_RECORDED_FRAMES in
# tests/world/test_gameplay_recording.py): 900 frames; K_UP
# tapped before frame 10 and K_RIGHT pressed before frame 70; the elevator called with K_w
# before frame 350; ESC pauses before frame 740 and SPACE resumes before frame 790
TOWER_RECORDED_FRAMES = 900
TOWER_FIRST_HOP_FRAME = 10
TOWER_WALK_RIGHT_FRAME = 70
TOWER_WALK_RIGHT_RELEASE_FRAME = 155
TOWER_ELEVATOR_CALL_FRAME = 350
TOWER_PAUSE_FRAME = 740
TOWER_RESUME_FRAME = 790
# How long each tap is held (clockwork_keep_script's held_frames)
HOP_HELD_FRAMES = 12
ELEVATOR_CALL_HELD_FRAMES = 4
# The ride, copied from Clockwork Keep's ELEVATOR_RIDE_DURATION and ELEVATOR_RIDE_EASING
# (src/games/clockwork-keep/src/clockwork_keep/constants.py:142-143): about 240 frames at 60 FPS
ELEVATOR_RIDE_SECONDS = 4.0
ELEVATOR_RIDE_EASING = 'ease_in_sine'
# A jump tapped during the ride, pressed and released before the same frame: that ride frame
# then drains two queued events, a press it discards and a release it delivers, in
# SceneManager._process_transition_events
TOWER_RIDE_HOP_FRAME = 450

# The climber's place and moves (pixels): it walks CLIMBER_STEP a frame while an arrow is held,
# and stands HOP_HEIGHT higher while the jump key is held
CLIMBER_START = (40, 300)
CLIMBER_SIZE = 12
CLIMBER_STEP = 2
HOP_HEIGHT = 30
CLIMBER_COLOR = (230, 180, 60)
FLOOR_COLORS = ((40, 30, 60), (30, 60, 40))


class Climber(pygame.sprite.DirtySprite):
    """A small screen-space sprite the tower floors move with the arrow and jump keys."""

    def __init__(self) -> None:
        """Create the climber at CLIMBER_START."""
        super().__init__()
        self.image = pygame.Surface((CLIMBER_SIZE, CLIMBER_SIZE))
        self.image.fill(CLIMBER_COLOR)
        self.rect = self.image.get_rect(topleft=CLIMBER_START)

    def update_nested_sprites(self) -> None:
        """Scene.update() calls this on every sprite; this sprite has no nested sprites."""

    def on_mouse_motion_event(self, event: pygame.event.Event) -> None:
        """The mouse manager calls this on the sprite under the pointer; it ignores it.

        On a real display the pointer can move over the test's window (x11 sends the motion).
        """


class TowerFloorScene(Scene):
    """A stand-in for a Clockwork Keep floor: walk, hop, ride the elevator, pause.

    The arrows walk the climber; holding K_UP lifts it (only after a press this scene saw);
    K_w on the ground floor rides the engine's ``ElevatorTransition`` to the upper floor; ESC
    pauses through the engine's ``PauseScene`` (``Scene.pause``), as Clockwork Keep does on the
    ESC press.
    """

    NAME = 'Tower Floor'
    VERSION = '1.0'
    FLOOR_INDEX = 0

    def __init__(self: Self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Add the climber on a floor of the floor's color."""
        super().__init__(options=options, groups=groups)
        self.background_color = FLOOR_COLORS[self.FLOOR_INDEX]
        self.climber = Climber()
        self.all_sprites.add(self.climber)
        self.walk_direction = 0
        self.is_hopping = False

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Walk the climber while an arrow is held."""
        super().dt_tick(dt)
        if self.walk_direction:
            self.climber.rect.x += self.walk_direction * CLIMBER_STEP
            self.climber.dirty = 1

    @override
    def on_key_down_event(self: Self, event: KeyEvent) -> None:
        """Walk, hop, call the elevator or pause; other keys go to the base scene."""
        if event.key == pygame.K_RIGHT:
            self.walk_direction = 1
        elif event.key == pygame.K_LEFT:
            self.walk_direction = -1
        elif event.key == pygame.K_UP:
            self.is_hopping = True
            self.climber.rect.y -= HOP_HEIGHT
            self.climber.dirty = 1
        elif event.key == pygame.K_w:
            self.call_elevator()
        elif event.key == pygame.K_ESCAPE:
            self.pause()
        else:
            super().on_key_down_event(event)

    @override
    def on_key_up_event(self: Self, event: KeyEvent) -> None:
        """Stop walking or land; other releases go to the base scene (never ESC: it paused)."""
        if event.key in {pygame.K_RIGHT, pygame.K_LEFT}:
            self.walk_direction = 0
        elif event.key == pygame.K_UP:
            # A release whose press this scene never saw (pressed during the ride) does nothing
            if self.is_hopping:
                self.is_hopping = False
                self.climber.rect.y += HOP_HEIGHT
                self.climber.dirty = 1
        elif event.key not in {pygame.K_w, pygame.K_ESCAPE}:
            super().on_key_up_event(event)

    def call_elevator(self: Self) -> None:
        """Ride the elevator to the upper floor (from the ground floor only)."""
        if self.FLOOR_INDEX == 0:
            self.transition_to(
                UpperTowerFloorScene(options=self.options),
                ElevatorTransition(duration=ELEVATOR_RIDE_SECONDS, easing=ELEVATOR_RIDE_EASING),
            )


class UpperTowerFloorScene(TowerFloorScene):
    """The floor the elevator arrives at."""

    NAME = 'Upper Tower Floor'
    FLOOR_INDEX = 1


def tower_script() -> InputScript:
    """The tower session's input: hops and walks, an elevator ride with a hop during it, a pause.

    Returns:
        The input script.

    """
    script = InputScript()
    script.tap(TOWER_FIRST_HOP_FRAME, pygame.K_UP, held_frames=HOP_HELD_FRAMES)
    script.at(TOWER_WALK_RIGHT_FRAME, press(pygame.K_RIGHT))
    script.at(TOWER_WALK_RIGHT_RELEASE_FRAME, release(pygame.K_RIGHT))
    script.tap(TOWER_ELEVATOR_CALL_FRAME, pygame.K_w, held_frames=ELEVATOR_CALL_HELD_FRAMES)
    script.at(TOWER_RIDE_HOP_FRAME, press(pygame.K_UP), release(pygame.K_UP))
    # Pause with ESC (press and release together) and resume with SPACE, as the golden scripts'
    # _pause_and_resume does (scripts/golden_inputs.py)
    script.at(TOWER_PAUSE_FRAME, press(pygame.K_ESCAPE), release(pygame.K_ESCAPE))
    script.at(TOWER_RESUME_FRAME, press(pygame.K_SPACE))
    script.at(TOWER_RESUME_FRAME + 2, release(pygame.K_SPACE))
    return script


# The steered paddle's place, size and step (pixels), and its script's key frames: up held from
# frame 5 to 20, down from 30 to 60, within the 120 frames the scripted session records
PADDLE_START = (40, 200)
PADDLE_SIZE = (8, 40)
PADDLE_STEP = 4
PADDLE_COLOR = (200, 200, 220)
STEER_UP_FRAME = 5
STEER_UP_RELEASE_FRAME = 20
STEER_DOWN_FRAME = 30
STEER_DOWN_RELEASE_FRAME = 60


class Paddle(pygame.sprite.DirtySprite):
    """A paddle the steered-paddle scene moves with the arrow keys."""

    def __init__(self) -> None:
        """Create the paddle at PADDLE_START."""
        super().__init__()
        self.image = pygame.Surface(PADDLE_SIZE)
        self.image.fill(PADDLE_COLOR)
        self.rect = self.image.get_rect(topleft=PADDLE_START)

    def update_nested_sprites(self) -> None:
        """Scene.update() calls this on every sprite; this sprite has no nested sprites."""

    def on_mouse_motion_event(self, event: pygame.event.Event) -> None:
        """The mouse manager calls this on the sprite under the pointer; it ignores it."""


class SteeredPaddleScene(Scene):
    """A stand-in for PaddleSlap's rally: a paddle steered up and down by the arrow keys."""

    NAME = 'Steered Paddle'
    VERSION = '1.0'

    def __init__(self: Self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Add the paddle."""
        super().__init__(options=options, groups=groups)
        self.paddle = Paddle()
        self.all_sprites.add(self.paddle)
        self.steer_direction = 0

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Move the paddle a fixed step while an arrow is held."""
        super().dt_tick(dt)
        if self.steer_direction:
            self.paddle.rect.y += self.steer_direction * PADDLE_STEP
            self.paddle.dirty = 1

    @override
    def on_key_down_event(self: Self, event: KeyEvent) -> None:
        """Steer with the arrows; other keys go to the base scene."""
        if event.key == pygame.K_UP:
            self.steer_direction = -1
        elif event.key == pygame.K_DOWN:
            self.steer_direction = 1
        else:
            super().on_key_down_event(event)

    @override
    def on_key_up_event(self: Self, event: KeyEvent) -> None:
        """Stop steering; other releases go to the base scene (Q and ESC quit there)."""
        if event.key in {pygame.K_UP, pygame.K_DOWN}:
            self.steer_direction = 0
        else:
            super().on_key_up_event(event)


def steered_paddle_script() -> InputScript:
    """The steered paddle's input: up, then down, by key events only.

    Returns:
        The input script.

    """
    script = InputScript()
    script.at(STEER_UP_FRAME, press(pygame.K_UP))
    script.at(STEER_UP_RELEASE_FRAME, release(pygame.K_UP))
    script.at(STEER_DOWN_FRAME, press(pygame.K_DOWN))
    script.at(STEER_DOWN_RELEASE_FRAME, release(pygame.K_DOWN))
    return script


# The sounding rally's frames and sounds: the long note plays from LONG_NOTE_FRAME, the burst
# from BURST_FRAME, more blips than the effects bus's channels (the library's 32 less the ui and
# music reservations of two each), so it steals
LONG_NOTE_FRAME = 2
LONG_NOTE_SECONDS = 0.6
BURST_FRAME = 12
BURST_PLAYS = 32
SOUNDING_RALLY_FRAMES = 48
BLIP_SECONDS = 0.2
LONG_NOTE_PRIORITY = 10
BURST_PRIORITY = 50
PROBE_SIZE = (4, 4)
PROBE_COLOR = (240, 200, 80)
MILLISECONDS_PER_SECOND = 1000
HUNDREDTHS = 100
PLAYING_PROBE_STEP = 2


class SoundProbe(pygame.sprite.DirtySprite):
    """A small sprite whose place shows a value the scene read of the audio engine."""

    def __init__(self) -> None:
        """Create the probe at the origin."""
        super().__init__()
        self.image = pygame.Surface(PROBE_SIZE)
        self.image.fill(PROBE_COLOR)
        self.rect = self.image.get_rect()
        self.dirty = 2

    def update_nested_sprites(self) -> None:
        """Scene.update() calls this on every sprite; this sprite has no nested sprites."""

    def on_mouse_motion_event(self, event: pygame.event.Event) -> None:
        """The mouse manager calls this on the sprite under the pointer; it ignores it."""


class SoundingRallyScene(Scene):
    """A stand-in for a game playing library sounds and reading what the engine says of them."""

    NAME = 'Sounding Rally'
    VERSION = '1.0'

    def __init__(self: Self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Add the three probes."""
        super().__init__(options=options, groups=groups)
        self.length_probe = SoundProbe()
        self.playing_probe = SoundProbe()
        self.burst_probe = SoundProbe()
        self.all_sprites.add(self.length_probe, self.playing_probe, self.burst_probe)
        self.frames_run = 0
        self.long_handle = None
        self.burst_handles: list[Any] = []

    @override
    def setup(self: Self) -> None:
        """Ask for the blip and the long note before the first frame."""
        audio = self.scene_manager.audio
        self.blip = audio.sound(
            Instrument(wave='square', envelope='pluck'), pitch='E5', length=BLIP_SECONDS
        )
        self.long_note = audio.sound(
            Instrument(wave='sine', envelope='organ'), pitch='A3', length=LONG_NOTE_SECONDS
        )

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Play on the scheduled frames, put what the engine says into the probes; maybe quit."""
        super().dt_tick(dt)
        if self.frames_run == LONG_NOTE_FRAME:
            self.long_handle = self.long_note.play(priority=LONG_NOTE_PRIORITY)
        if self.frames_run == BURST_FRAME:
            self.burst_handles = [
                self.blip.play(priority=BURST_PRIORITY) for _ in range(BURST_PLAYS)
            ]
        self.length_probe.rect.topleft = (
            round(self.blip.length * MILLISECONDS_PER_SECOND),
            round(self.blip.peak * HUNDREDTHS),
        )
        if self.long_handle is not None and self.long_handle.is_playing:
            self.playing_probe.rect.x += PLAYING_PROBE_STEP
        self.burst_probe.rect.topleft = (
            sum(1 for handle in self.burst_handles if handle.is_playing),
            self.scene_manager.audio.diagnostics().stolen_voices,
        )
        self.frames_run += 1
        if self.frames_run == SOUNDING_RALLY_FRAMES:
            self.scene_manager.quit()


# The pad readout's marker: its x is PAD_READOUT_ORIGIN_X plus PAD_READOUT_SCALE times the pad's
# axis 0 (rounded), so an axis at 0.5 puts it at 150
PAD_READOUT_ORIGIN_X = 100
PAD_READOUT_SCALE = 100
PAD_READOUT_Y = 120
PAD_READOUT_SIZE = (6, 6)
PAD_READOUT_COLOR = (120, 220, 160)


class PadReadoutMarker(pygame.sprite.DirtySprite):
    """A small sprite whose place shows the stand-in pad's axis 0."""

    def __init__(self) -> None:
        """Create the marker at the axis's rest position."""
        super().__init__()
        self.image = pygame.Surface(PAD_READOUT_SIZE)
        self.image.fill(PAD_READOUT_COLOR)
        self.rect = self.image.get_rect(topleft=(PAD_READOUT_ORIGIN_X, PAD_READOUT_Y))
        self.dirty = 2

    def update_nested_sprites(self) -> None:
        """Scene.update() calls this on every sprite; this sprite has no nested sprites."""

    def on_mouse_motion_event(self, event: pygame.event.Event) -> None:
        """The mouse manager calls this on the sprite under the pointer; it ignores it."""


class PadReadoutScene(Scene):
    """A stand-in for a game read from a pad: its marker follows the pad's polled axis 0.

    Its facts: it reads the stand-in stick (``STAND_IN_STICK``, tests/input/stand_in_devices.py)
    from the frame's polled input only (``current_input()``), so a session of it needs
    ``polled_input``; the marker is a sprite on every frame, its x
    ``PAD_READOUT_ORIGIN_X + round(PAD_READOUT_SCALE * axis 0)``, so a replay compares what the
    pad did. Its pad's events change nothing of its own.
    """

    NAME = 'Pad Readout'
    VERSION = '1.0'

    def __init__(self: Self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Add the marker."""
        super().__init__(options=options, groups=groups)
        self.marker = PadReadoutMarker()
        self.all_sprites.add(self.marker)

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Put the pad's axis 0 into the marker's x."""
        super().dt_tick(dt)
        axis_position = current_input().axis(device_id=STAND_IN_STICK.instance_id, axis=0)
        self.marker.rect.x = PAD_READOUT_ORIGIN_X + round(PAD_READOUT_SCALE * axis_position)
