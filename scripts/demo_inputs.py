"""The bundled demos' own input scripts.

A bundled demo (scripts/record_bundled_demos.py) is the first frames of a game's golden input
script (scripts/golden_inputs.py) whenever that script's frames already make a good demo. A game
whose script holds a key to the last frame needs a demo script of its own, which lives here: each
builder takes no arguments and returns a fresh ``InputScript``, a ``MODULE:NAME`` target for a
recipe's ``script`` (``scripts.demo_inputs:mr_muncher_demo_script``). The golden scripts and the
golden replays are never changed for a demo.

Why a demo needs its own: the Arcade loops a demo, so nothing a demo pressed may still be down
after its last frame (tests/replay/test_bundled_demos.py
``test_no_bundled_demo_ends_with_input_held``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from glitchygames.replay.tools.golden_traces import InputScript, release
from scripts.golden_inputs import MuncherSteering, mr_muncher_script

if TYPE_CHECKING:
    import pygame

    from glitchygames.scenes import Scene

# Mr. Muncher's chase: how many frames of the golden script it records. Its autopilot holds an
# arrow key at every frame from the first on (the golden script is quiet only in its controls
# tail, which a demo has none of), so no shorter count leaves nothing held: the demo's steering
# releases the held key on its last frame instead (ReleaseHeldKeyOnFinalFrame)
MR_MUNCHER_DEMO_FRAME_COUNT = 1950


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
