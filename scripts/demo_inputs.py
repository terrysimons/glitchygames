"""The bundled demos' own input scripts.

A bundled demo (scripts/record_bundled_demos.py) is the first frames of a game's golden input
script (scripts/golden_inputs.py) whenever that script's frames already make a good demo. A game
whose script holds a key to the last frame needs a demo script of its own, which lives here: each
builder takes no arguments and returns a fresh ``InputScript``, a ``MODULE:NAME`` target for a
recipe's ``script`` (``scripts.demo_inputs:mr_muncher_demo_script``). The golden scripts and the
golden replays are never changed for a demo. A demo of a game with no golden script (the dt demo
and the text-input demo, which are demos-layer members, not games) has a script here too.

Why a demo needs its own: the Arcade loops a demo, so nothing a demo pressed may still be down
after its last frame (tests/replay/test_bundled_demos.py
``test_no_bundled_demo_ends_with_input_held``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pygame

from glitchygames.replay.tools.golden_traces import InputScript, release
from glitchygames.testing.keys import qwerty_scancode
from scripts.golden_inputs import MuncherSteering, mr_muncher_script

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
