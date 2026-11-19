"""Whether the intro opens this launch: wherever the CRT power-on would play (feature plan 12).

The intro plays at every launch, before the title (the owner, 2026-11-19: "lets always run it
then, but let the user skip with a button press"), and only where someone can see it and
nothing is recorded or replayed: the same rule as the engine's CRT power-on
(``glitchygames.crt_power_on``: not on the dummy video driver, not with ``--replay-trace``,
``--record-trace``, ``--audit`` or ``--rebaseline``, not with ``--crt-power-on off``). The game
asks the engine's public functions the engine's own question, because the engine keeps its
answer private and the game may not change the engine (decision 12; a public answer is on the
master plan's wishlist).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pygame

from glitchygames import crt_power_on

if TYPE_CHECKING:
    from collections.abc import Mapping


def current_video_driver() -> str:
    """Return SDL's video driver (the one place tests stand a real driver in for the dummy).

    Returns:
        The driver's name (``dummy`` when nobody can see the screen).
    """
    return pygame.display.get_driver()


def launch_showing_allowed(*, options: Mapping[str, Any], video_driver: str) -> bool:
    """Return whether the intro opens this run, as the CRT power-on would play.

    Args:
        options: The run's options.
        video_driver: SDL's video driver.

    Returns:
        True to show it.
    """
    mode = crt_power_on.resolve_mode(option=options.get('crt_power_on'), environment=os.environ)
    return crt_power_on.should_play(mode=mode, video_driver=video_driver, options=options)
