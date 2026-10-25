"""The CRT power-on sequence: every game's canvas switches on like an analogue TV first.

Before control is handed to the game (``GameEngine._prepare_run``, so every game, Bitmappy
included), its canvas shows a CRT switching on: black, a bright dot in the centre, the dot
stretched into a line, the picture opening from the line, a warm-up flicker, then the
configured default background (glitchygames/backgrounds.py: the TV test pattern or the channel
3 screen). ``--crt-power-on`` chooses when it plays (``should_play``):

- ``auto`` (the default): when someone can see it and nothing is disturbed: not on SDL's dummy
  video driver (``--headless``, every test), and not before a replay, an audit, a rebaseline
  or a recording (events pumped before frame 0 would be input the game never saw);
- ``on``: always (refused with a replay or a recording); ``off``: never.

Rules it keeps: visual only, before the game's first scene exists, so it changes no game state,
random stream, frame clock or scene clock, and is never in a recording or screenshot. It uses
no randomness: the flicker is a fixed table. Events are taken only through the doors and
dropped, except that a key or button press skips the rest and a QUIT is handed back to the
game, which then quits.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

# The SDL video driver nobody can see (--headless; every test)
INVISIBLE_VIDEO_DRIVER = 'dummy'
# Options whose run must not have anything happen before frame 0
RUN_RECORDED_OR_REPLAYED_OPTIONS = ('replay_trace', 'record_trace', 'audit', 'rebaseline')


class CrtPowerOnMode(enum.StrEnum):
    """When the power-on sequence plays (``--crt-power-on``)."""

    AUTO = 'auto'
    ON = 'on'
    OFF = 'off'


def should_play(*, mode: CrtPowerOnMode, video_driver: str, options: Mapping[str, Any]) -> bool:
    """Return whether the power-on sequence plays for this run.

    Args:
        mode: ``--crt-power-on``.
        video_driver: SDL's video driver (``pygame.display.get_driver()``).
        options: The run's options.

    Returns:
        True to play it.

    """
    if mode is CrtPowerOnMode.ON:
        return True
    if mode is CrtPowerOnMode.OFF:
        return False
    if video_driver == INVISIBLE_VIDEO_DRIVER:
        return False
    return not any(options.get(name) for name in RUN_RECORDED_OR_REPLAYED_OPTIONS)
