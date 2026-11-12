"""The bundled demos' own input scripts.

A bundled demo (scripts/record_bundled_demos.py) is the first frames of a game's golden input
script (scripts/golden_inputs.py) whenever that script's frames already make a good demo. A game
whose script holds a key to the last frame needs a demo script of its own, which lives here: each
builder takes no arguments and returns a fresh ``InputScript``, a ``MODULE:NAME`` target for a
recipe's ``script`` (``scripts.demo_inputs:mr_muncher_demo_script``). The golden scripts and the
golden replays are never changed for a demo. A demo of a game with no golden script (the dt demo,
the joystick demo and the text-input demo, which are demos-layer members, not games, and
Bitmappy, an app) has a script here too.

The joystick demo's pad is a stand-in (``DEMO_PAD``, glitchygames/input/stand_in_devices.py): it
exists only in the recording session, whose recipe names it (``DemoRecipe.stand_in_devices``), so
its script posts the pad's own events (JOYAXISMOTION, JOYBUTTONDOWN/UP, JOYHATMOTION by its
instance id), which the recorder follows into the frame's polled input (``polled_input=True``).

Why a demo needs its own: the Arcade loops a demo, so nothing a demo pressed may still be down
after its last frame (tests/replay/test_bundled_demos.py
``test_no_bundled_demo_ends_with_input_held``). The joystick demo's pad also ends at rest: every
axis back at 0 and the hat centred.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Protocol

import pygame

from glitchygames.input.devices import JOYSTICK_KIND, DeviceDescriptor
from glitchygames.replay.tools.golden_traces import InputScript, release
from glitchygames.testing.keys import qwerty_scancode
from scripts.golden_inputs import LEFT_MOUSE_BUTTON, MuncherSteering, mr_muncher_script

if TYPE_CHECKING:
    from glitchygames.scenes import Scene

# Mr. Muncher's chase: how many frames of the golden script it records. Its autopilot holds an
# arrow key at every frame from the first on (the golden script is quiet only in its controls
# tail, which a demo has none of), so no shorter count leaves nothing held: the demo's steering
# releases the held key on its last frame instead (ReleaseHeldKeyOnFinalFrame)
MR_MUNCHER_DEMO_FRAME_COUNT = 1950
# The dt demo: the frame Space is pressed before (the "Time" line is still 0 until then) and how
# long it is held. The square crosses at 300 pixels a second, so the record line shows well
# before the 600th frame
DT_DEMO_SPACE_FRAME = 30
DT_DEMO_SPACE_HELD_FRAMES = 3
DT_DEMO_FRAME_COUNT = 600

# The text-input demo: Tab (released) focuses the box, which starts with the text "Test"; each
# key is held a few frames and the next one is pressed a pace later; Return submits
TEXT_INPUT_DEMO_TEXT = 'GLITCHYGAMES'
TEXT_INPUT_DEMO_ORIGINAL_TEXT_LENGTH = len('Test')
TEXT_INPUT_DEMO_FOCUS_FRAME = 20
TEXT_INPUT_DEMO_FIRST_KEY_FRAME = 50
TEXT_INPUT_DEMO_FRAMES_BETWEEN_KEYS = 15
TEXT_INPUT_DEMO_KEY_HELD_FRAMES = 4
TEXT_INPUT_DEMO_FRAME_COUNT = 600

# The joystick demo's pad: an unmapped joystick (its events come from its joystick layer, axes
# -1.0..1.0) that exists only in the recording session. It names no GUID, so the readout shows
# "GUID: unknown"
DEMO_PAD = DeviceDescriptor(
    kind=JOYSTICK_KIND,
    device_index=0,
    instance_id=0,
    name='GlitchyGames Demo Pad',
    guid=None,
    axis_count=6,
    button_count=12,
    hat_count=1,
    ball_count=0,
)
# The joystick demo's script, one part after another: each axis in turn swept through a full
# sine cycle (0, up to 1.0, down to -1.0, back to 0) one position a frame; then each button
# pressed, held and released, the next a pace later; then the hat round its eight positions,
# clockwise from up, and back to centre; then the pad stays at rest to the last frame
JOYSTICK_DEMO_FIRST_AXIS_FRAME = 30
JOYSTICK_DEMO_AXIS_SWEEP_FRAMES = 40
# Decimal places of a swept axis's positions (the readout's text shows each)
JOYSTICK_DEMO_AXIS_DECIMAL_PLACES = 3
JOYSTICK_DEMO_FIRST_BUTTON_FRAME = 290
JOYSTICK_DEMO_FRAMES_BETWEEN_BUTTONS = 12
JOYSTICK_DEMO_BUTTON_HELD_FRAMES = 8
JOYSTICK_DEMO_FIRST_HAT_FRAME = 450
JOYSTICK_DEMO_HAT_HELD_FRAMES = 10
# (x, y): pygame's hat values, y up
JOYSTICK_DEMO_HAT_POSITIONS = ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1))
JOYSTICK_DEMO_HAT_CENTRE = (0, 0)
JOYSTICK_DEMO_FRAME_COUNT = 600

# Bitmappy's demo: a smiley drawn on the blank 32x32 canvas. The points are the editor's layout
# at the recorder's resolution (SCREEN_RESOLUTION, 800x480): the canvas's top-left corner is
# below the menu bar, each canvas pixel a 10-pixel square
# (src/apps/bitmappy/tests/test_bitmappy_demo_script.py checks every point on the real editor)
BITMAPPY_DEMO_CANVAS_LEFT = 0
BITMAPPY_DEMO_CANVAS_TOP = 24
BITMAPPY_DEMO_CANVAS_PIXEL_SIZE = 10
# The colours: the editor starts with white; the blue slider's left end makes it yellow, then the
# red and the green sliders' left ends make it black
BITMAPPY_DEMO_FACE_COLOR = (255, 255, 0)
BITMAPPY_DEMO_FEATURE_COLOR = (0, 0, 0)
# (channel, point): each a click on the left end of a slider (its value goes to 0); the
# sliders' rows at 800x480 are red y 443-451, green 456-464, blue 469-477, from x 13
BITMAPPY_DEMO_FACE_COLOR_PICKS = (('blue', (13, 473)),)
BITMAPPY_DEMO_FEATURE_COLOR_PICKS = (('red', (13, 447)), ('green', (13, 460)))
BITMAPPY_DEMO_COLOR_PICKS = (*BITMAPPY_DEMO_FACE_COLOR_PICKS, *BITMAPPY_DEMO_FEATURE_COLOR_PICKS)
# The face, a 16-pixel disc, one drag per row: (row, first column, last column)
BITMAPPY_DEMO_FACE_ROWS = (
    (7, 13, 18),
    (8, 11, 20),
    (9, 10, 21),
    (10, 9, 22),
    (11, 8, 23),
    (12, 8, 23),
    (13, 8, 23),
    (14, 8, 23),
    (15, 8, 23),
    (16, 8, 23),
    (17, 8, 23),
    (18, 8, 23),
    (19, 9, 22),
    (20, 10, 21),
    (21, 11, 20),
    (22, 13, 18),
)
# The features over the face, one drag each through its (column, row) pixels in order: the eyes
# (two pixels square) and the smile. A drag paints only the pixels its motions reach, so every
# pixel of a stroke is named
BITMAPPY_DEMO_FEATURE_STROKES = (
    ((11, 11), (12, 11), (12, 12), (11, 12)),
    ((19, 11), (20, 11), (20, 12), (19, 12)),
    (
        (10, 16),
        (11, 17),
        (12, 18),
        (13, 19),
        (14, 19),
        (15, 19),
        (16, 19),
        (17, 19),
        (18, 19),
        (19, 18),
        (20, 17),
        (21, 16),
    ),
)
# The pace: a colour pick's click is held a few frames; a drag moves one pixel every
# BITMAPPY_DEMO_FRAMES_PER_PIXEL frames, and the next drag starts a pause after the last one's
# release. The finished smiley stays on the canvas for the demo's last frames
BITMAPPY_DEMO_FIRST_PICK_FRAME = 30
BITMAPPY_DEMO_CLICK_HELD_FRAMES = 4
BITMAPPY_DEMO_FRAMES_BETWEEN_PICKS = 20
BITMAPPY_DEMO_FRAMES_PER_PIXEL = 2
BITMAPPY_DEMO_FRAMES_BETWEEN_STROKES = 4
BITMAPPY_DEMO_FRAME_COUNT = 900


class HoldingSteering(Protocol):
    """A per-frame steering that remembers the one key it holds (``MuncherSteering``)."""

    held_key: int | None

    def __call__(self, scene: Scene) -> list[pygame.event.Event]:
        """Return the key events that steer the game this frame."""
        ...


class ReleaseHeldKeyOnFinalFrame:
    """A per-frame steering that lets go of its key on the demo's last frame and presses no more.

    A per-frame input of an InputScript is called once per frame from the supervisor slot of
    frame 0 on, each call posting input for the next frame (the first call is for frame 1), so
    the call number is the frame the events arrive before. On ``final_frame`` the held key's
    release is posted (a KEYUP built by ``release``, with the key's scancode) instead of the
    steering's own events; before it the steering is called as it always is, after it nothing is
    posted.

    Attributes:
        steering: The steering this wraps.
        final_frame: The frame the key is released before (the demo's last frame).
        calls: How many times this has been called.
    """

    def __init__(self, *, steering: HoldingSteering, final_frame: int) -> None:
        """Wrap a steering.

        Args:
            steering: The golden script's steering.
            final_frame: The frame the held key is released before.

        """
        self.steering = steering
        self.final_frame = final_frame
        self.calls = 0

    def __call__(self, scene: Scene) -> list[pygame.event.Event]:
        """Return the events for the next frame.

        Args:
            scene: The active scene.

        Returns:
            The steering's events before the final frame, the held key's release on it, and
            nothing after it.

        """
        self.calls += 1
        if self.calls < self.final_frame:
            return self.steering(scene)
        if self.calls > self.final_frame:
            return []
        held_key = self.steering.held_key
        self.steering.held_key = None
        return [] if held_key is None else [release(held_key)]


def mr_muncher_demo_script() -> InputScript:
    """Mr. Muncher's chase demo: the golden script, its steering letting go on the last frame.

    Returns:
        The golden script (scripts/golden_inputs.py ``mr_muncher_script``: the autopilot's
        steering, the pause and resume) with its steering wrapped to release the held arrow key
        before frame ``MR_MUNCHER_DEMO_FRAME_COUNT - 1``.

    Raises:
        TypeError: If the golden script's per-frame input is not a ``MuncherSteering``.

    """
    script = mr_muncher_script()
    if not isinstance(script.per_frame, MuncherSteering):
        message = 'the golden Mr. Muncher script has no MuncherSteering as its per-frame input'
        raise TypeError(message)
    script.per_frame = ReleaseHeldKeyOnFinalFrame(
        steering=script.per_frame,
        final_frame=MR_MUNCHER_DEMO_FRAME_COUNT - 1,
    )
    return script


def dt_demo_script() -> InputScript:
    """The dt demo: Space starts the square, which then crosses the screen.

    Returns:
        A script that presses Space before ``DT_DEMO_SPACE_FRAME`` and releases it
        ``DT_DEMO_SPACE_HELD_FRAMES`` later. The demo reads Space from the frame's polled input,
        so its recipe records with ``polled_input=True``.

    """
    script = InputScript()
    script.tap(DT_DEMO_SPACE_FRAME, pygame.K_SPACE, held_frames=DT_DEMO_SPACE_HELD_FRAMES)
    return script


def joystick_demo_axis_sweep() -> tuple[float, ...]:
    """Return a swept axis's positions, one a frame: a full sine cycle ending exactly at rest.

    Returns:
        ``JOYSTICK_DEMO_AXIS_SWEEP_FRAMES`` positions, each rounded to
        ``JOYSTICK_DEMO_AXIS_DECIMAL_PLACES``: up to 1.0 a quarter of the way through, down to
        -1.0 at three quarters, and 0.0 last (never -0.0, which a recording would write as such).

    """
    positions: list[float] = []
    for step in range(1, JOYSTICK_DEMO_AXIS_SWEEP_FRAMES + 1):
        position = round(
            math.sin(2 * math.pi * step / JOYSTICK_DEMO_AXIS_SWEEP_FRAMES),
            JOYSTICK_DEMO_AXIS_DECIMAL_PLACES,
        )
        positions.append(position if position != 0 else 0.0)
    return tuple(positions)


def joystick_demo_script() -> InputScript:
    """The joystick demo: the demo pad sweeps every axis, presses every button, works the hat.

    Returns:
        A script of ``DEMO_PAD``'s own events: from ``JOYSTICK_DEMO_FIRST_AXIS_FRAME`` each axis
        in turn takes ``joystick_demo_axis_sweep``'s positions, one JOYAXISMOTION a frame; from
        ``JOYSTICK_DEMO_FIRST_BUTTON_FRAME`` each button is pressed and released
        ``JOYSTICK_DEMO_BUTTON_HELD_FRAMES`` later, one every
        ``JOYSTICK_DEMO_FRAMES_BETWEEN_BUTTONS`` frames; from ``JOYSTICK_DEMO_FIRST_HAT_FRAME``
        the hat holds each of ``JOYSTICK_DEMO_HAT_POSITIONS`` for
        ``JOYSTICK_DEMO_HAT_HELD_FRAMES`` frames, then centres. The demo draws its gauges from
        the frame's polled input, so the recipe records with ``polled_input=True``.

    """
    script = InputScript()
    instance_id = DEMO_PAD.instance_id
    frame_number = JOYSTICK_DEMO_FIRST_AXIS_FRAME
    for axis in range(DEMO_PAD.axis_count):
        for position in joystick_demo_axis_sweep():
            script.at(
                frame_number,
                pygame.event.Event(
                    pygame.JOYAXISMOTION, instance_id=instance_id, axis=axis, value=position
                ),
            )
            frame_number += 1
    frame_number = JOYSTICK_DEMO_FIRST_BUTTON_FRAME
    for button in range(DEMO_PAD.button_count):
        script.at(
            frame_number,
            pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=instance_id, button=button),
        )
        script.at(
            frame_number + JOYSTICK_DEMO_BUTTON_HELD_FRAMES,
            pygame.event.Event(pygame.JOYBUTTONUP, instance_id=instance_id, button=button),
        )
        frame_number += JOYSTICK_DEMO_FRAMES_BETWEEN_BUTTONS
    frame_number = JOYSTICK_DEMO_FIRST_HAT_FRAME
    for hat_position in (*JOYSTICK_DEMO_HAT_POSITIONS, JOYSTICK_DEMO_HAT_CENTRE):
        script.at(
            frame_number,
            pygame.event.Event(
                pygame.JOYHATMOTION, instance_id=instance_id, hat=0, value=hat_position
            ),
        )
        frame_number += JOYSTICK_DEMO_HAT_HELD_FRAMES
    return script


def typed_key_events(*, character: str) -> tuple[pygame.event.Event, pygame.event.Event]:
    """Build the key down and key up of one typed character, as a real keyboard reports them.

    Args:
        character: One letter. An upper-case one carries Shift in ``mod``.

    Returns:
        ``(KEYDOWN, KEYUP)``: the key is the lower-case letter's, its ``unicode`` the character,
        its scancode the key's US QWERTY position.

    """
    key = ord(character.lower())
    modifiers = pygame.KMOD_LSHIFT if character.isupper() else 0
    scancode = qwerty_scancode(key=key)
    key_down = pygame.event.Event(
        pygame.KEYDOWN, key=key, mod=modifiers, unicode=character, scancode=scancode
    )
    key_up = pygame.event.Event(
        pygame.KEYUP, key=key, mod=modifiers, unicode=character, scancode=scancode
    )
    return key_down, key_up


def text_input_demo_script() -> InputScript:
    """The text-input demo: focus the box, clear "Test", type GLITCHYGAMES, submit it.

    Returns:
        A script that taps Tab (the scene focuses the box on its release), taps Backspace once
        for each letter of the box's starting text, types ``TEXT_INPUT_DEMO_TEXT`` a letter every
        ``TEXT_INPUT_DEMO_FRAMES_BETWEEN_KEYS`` frames and taps Return. Every key is released
        ``TEXT_INPUT_DEMO_KEY_HELD_FRAMES`` frames after its press. The box reads each KEYDOWN's
        ``unicode`` (it reads no TEXTINPUT event), so none is posted.

    """
    script = InputScript()
    script.tap(
        TEXT_INPUT_DEMO_FOCUS_FRAME, pygame.K_TAB, held_frames=TEXT_INPUT_DEMO_KEY_HELD_FRAMES
    )
    frame_number = TEXT_INPUT_DEMO_FIRST_KEY_FRAME
    for _ in range(TEXT_INPUT_DEMO_ORIGINAL_TEXT_LENGTH):
        script.tap(frame_number, pygame.K_BACKSPACE, held_frames=TEXT_INPUT_DEMO_KEY_HELD_FRAMES)
        frame_number += TEXT_INPUT_DEMO_FRAMES_BETWEEN_KEYS
    for character in TEXT_INPUT_DEMO_TEXT:
        key_down, key_up = typed_key_events(character=character)
        script.at(frame_number, key_down)
        script.at(frame_number + TEXT_INPUT_DEMO_KEY_HELD_FRAMES, key_up)
        frame_number += TEXT_INPUT_DEMO_FRAMES_BETWEEN_KEYS
    script.tap(frame_number, pygame.K_RETURN, held_frames=TEXT_INPUT_DEMO_KEY_HELD_FRAMES)
    return script


def bitmappy_demo_canvas_point(*, column: int, row: int) -> tuple[int, int]:
    """Return the window point at the centre of a canvas pixel's square, at 800x480.

    Args:
        column: The canvas pixel's column.
        row: The canvas pixel's row.

    Returns:
        ``(x, y)`` in window pixels.

    """
    half_pixel = BITMAPPY_DEMO_CANVAS_PIXEL_SIZE // 2
    return (
        BITMAPPY_DEMO_CANVAS_LEFT + column * BITMAPPY_DEMO_CANVAS_PIXEL_SIZE + half_pixel,
        BITMAPPY_DEMO_CANVAS_TOP + row * BITMAPPY_DEMO_CANVAS_PIXEL_SIZE + half_pixel,
    )


def bitmappy_demo_face_strokes() -> tuple[tuple[tuple[int, int], ...], ...]:
    """Return the face's drags as canvas pixels, one per row, alternating direction.

    Returns:
        Each row's ``(column, row)`` pixels, the first row left to right, the next right to
        left, and so on, as a hand going back and forth would fill it.

    """
    return tuple(
        tuple(
            (column, row)
            for column in (range(first, last + 1) if index % 2 == 0 else range(last, first - 1, -1))
        )
        for index, (row, first, last) in enumerate(BITMAPPY_DEMO_FACE_ROWS)
    )


# Every point the demo clicks or drags through on the canvas, in the order it does
BITMAPPY_DEMO_POINTS: tuple[tuple[int, int], ...] = tuple(
    bitmappy_demo_canvas_point(column=column, row=row)
    for stroke in (*bitmappy_demo_face_strokes(), *BITMAPPY_DEMO_FEATURE_STROKES)
    for column, row in stroke
)


def mouse_motion(
    *, position: tuple[int, int], previous_position: tuple[int, int], is_button_down: bool
) -> pygame.event.Event:
    """Build a mouse motion as a real mouse reports it.

    Args:
        position: Where the pointer moves to.
        previous_position: Where it was.
        is_button_down: True while the left button is held (a drag).

    Returns:
        A MOUSEMOTION with its ``rel`` and ``buttons``.

    """
    return pygame.event.Event(
        pygame.MOUSEMOTION,
        pos=position,
        rel=(position[0] - previous_position[0], position[1] - previous_position[1]),
        buttons=(int(is_button_down), 0, 0),
        touch=False,
    )


def mouse_button(*, position: tuple[int, int], is_down: bool) -> pygame.event.Event:
    """Build a left mouse button press or release.

    Args:
        position: Where the pointer is.
        is_down: True for the press, False for the release.

    Returns:
        A MOUSEBUTTONDOWN or MOUSEBUTTONUP of the left button.

    """
    return pygame.event.Event(
        pygame.MOUSEBUTTONDOWN if is_down else pygame.MOUSEBUTTONUP,
        pos=position,
        button=LEFT_MOUSE_BUTTON,
        touch=False,
    )


class BitmappyDemoHand:
    """Writes a pointer's moves, clicks and drags into an input script, frame by frame.

    Attributes:
        script: The script the events go into.
        frame_number: The frame the next event is posted before.
        position: Where the pointer is.
    """

    def __init__(self, *, script: InputScript, frame_number: int) -> None:
        """Start with the pointer at the window's top-left corner and the button up.

        Args:
            script: The script to write into.
            frame_number: The first frame to post before.

        """
        self.script = script
        self.frame_number = frame_number
        self.position = (0, 0)

    def move_to(self, *, position: tuple[int, int], is_button_down: bool) -> None:
        """Move the pointer before the current frame.

        Args:
            position: Where it moves to.
            is_button_down: True while the left button is held.

        """
        self.script.at(
            self.frame_number,
            mouse_motion(
                position=position,
                previous_position=self.position,
                is_button_down=is_button_down,
            ),
        )
        self.position = position

    def click(self, *, position: tuple[int, int]) -> None:
        """Move to a point and click it: pressed, held a few frames, released, then a pause.

        Args:
            position: The point.

        """
        self.move_to(position=position, is_button_down=False)
        self.script.at(self.frame_number, mouse_button(position=position, is_down=True))
        self.frame_number += BITMAPPY_DEMO_CLICK_HELD_FRAMES
        self.script.at(self.frame_number, mouse_button(position=position, is_down=False))
        self.frame_number += BITMAPPY_DEMO_FRAMES_BETWEEN_PICKS

    def drag(self, *, positions: tuple[tuple[int, int], ...]) -> None:
        """Press at the first point, move through the rest with the button held, release.

        Args:
            positions: The points, in order.

        """
        first_position, *later_positions = positions
        self.move_to(position=first_position, is_button_down=False)
        self.script.at(self.frame_number, mouse_button(position=first_position, is_down=True))
        for position in later_positions:
            self.frame_number += BITMAPPY_DEMO_FRAMES_PER_PIXEL
            self.move_to(position=position, is_button_down=True)
        self.frame_number += BITMAPPY_DEMO_FRAMES_PER_PIXEL
        self.script.at(self.frame_number, mouse_button(position=self.position, is_down=False))
        self.frame_number += BITMAPPY_DEMO_FRAMES_BETWEEN_STROKES


def bitmappy_demo_script() -> InputScript:
    """Bitmappy's demo: pick yellow, draw a face, pick black, draw its eyes and smile.

    Returns:
        A script that clicks the left end of the blue slider (white becomes yellow), drags
        across each row of ``BITMAPPY_DEMO_FACE_ROWS``, clicks the left ends of the red and green
        sliders (yellow becomes black) and drags through each of
        ``BITMAPPY_DEMO_FEATURE_STROKES``, from ``BITMAPPY_DEMO_FIRST_PICK_FRAME`` on. Every
        press is released. The canvas paints from the mouse events (their positions), never
        from the polled mouse, so the recipe records without ``polled_input``.

    """
    script = InputScript()
    hand = BitmappyDemoHand(script=script, frame_number=BITMAPPY_DEMO_FIRST_PICK_FRAME)
    for _channel, position in BITMAPPY_DEMO_FACE_COLOR_PICKS:
        hand.click(position=position)
    for stroke in bitmappy_demo_face_strokes():
        hand.drag(
            positions=tuple(
                bitmappy_demo_canvas_point(column=column, row=row) for column, row in stroke
            )
        )
    hand.frame_number += BITMAPPY_DEMO_FRAMES_BETWEEN_PICKS
    for _channel, position in BITMAPPY_DEMO_FEATURE_COLOR_PICKS:
        hand.click(position=position)
    for stroke in BITMAPPY_DEMO_FEATURE_STROKES:
        hand.drag(
            positions=tuple(
                bitmappy_demo_canvas_point(column=column, row=row) for column, row in stroke
            )
        )
    return script
