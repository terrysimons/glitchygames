"""The audio route per engine context: whether the context's sound is heard.

Only one context is heard at a time (Arcade sub-plan 4, plans/2026-11-13-arcade-4-sound.md,
decision 1): the default context (an ordinary game, or the Arcade itself) is audible, and an
inner game's context starts silent (``InnerGame``, glitchygames/inner_game.py, makes it so when
it creates the context; its host switches one at a time audible). The flag says only whether the
context may reach the mixer; what the game sees (a handle's ``is_playing``, a voice's end, a
steal) is the same heard or silent, so a silent game replays as it does alone.

The engine keeps a silent context off the mixer at each way sound reaches it: plain
``Sound.play()`` finds every channel reserved while a silent inner game builds, steps or
finishes (``glitchygames.audio.voices.every_channel_reserved``, applied by ``InnerGame``).
"""

from __future__ import annotations

from typing import Self

from glitchygames.engine_context import ContextSlot, current_context


class AudioRoute:
    """One context's audio route.

    A plain class, not a frozen model: it is changed in place.

    Attributes:
        audible: True when the context's sound is heard (the default); False when it is kept off
            the mixer.

    """

    def __init__(self: Self) -> None:
        """Start audible, as an ordinary game is."""
        self.audible: bool = True


AUDIO_ROUTE_SLOT: ContextSlot[AudioRoute] = ContextSlot(
    name='glitchygames.audio.route.audio_route', factory=AudioRoute
)


def is_audible() -> bool:
    """Tell whether the current context's sound is heard.

    Returns:
        True when the current context is audible (the default context always starts so).

    """
    return current_context().value(slot=AUDIO_ROUTE_SLOT).audible


def set_audible(*, audible: bool) -> None:
    """Make the current context's sound heard or silent.

    Args:
        audible: True to hear the context's sound, False to keep it off the mixer.

    """
    current_context().value(slot=AUDIO_ROUTE_SLOT).audible = audible
