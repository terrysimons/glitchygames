"""The audio route per engine context: whether the context's sound is heard.

Only one context is heard at a time (Arcade sub-plan 4, plans/2026-11-13-arcade-4-sound.md,
decision 1): the default context (an ordinary game, or the Arcade itself) is audible, and an
inner game's context starts silent (``InnerGame``, glitchygames/inner_game.py, makes it so when
it creates the context; its host switches one at a time audible). The flag says only whether the
context may reach the mixer; what the game sees (a handle's ``is_playing``, a voice's end, a
steal) is the same heard or silent, so a silent game replays as it does alone.

The engine keeps a silent context off the mixer at each way sound reaches it: plain
``Sound.play()`` finds every channel reserved while a silent inner game builds, steps or
finishes (``glitchygames.audio.voices.every_channel_reserved``, applied by ``InnerGame``); the
``AudioEngine``'s voice table makes no mixer call while its context is silent
(``glitchygames.audio.voices``, decision 3); the old live voices' chunks play at volume 0
(``glitchygames.audio.live``). When an audible context goes silent (the heard game changes,
decision 6), what it still has sounding is taken off the mixer: its voices fade over 50 ms, its
plain plays (followed while it was audible: ``voices.plain_plays_followed``) are stopped and its
live chunks muted.
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

    Going silent fades the context's heard voices first, while it is still audible, through its
    audio engine if it has one (``AudioEngine.fade_out_of_the_mixer``: the scene clean-up's 50 ms
    fade; no engine is made just to tell it), then stops the plain ``Sound.play()`` sounds it
    started that still play and mutes its live pool's chunks (decision 6:
    ``voices.stop_plain_plays_and_mute_the_live_pool``; never another context's sound), and only
    then turns the route silent, after which the voice table makes no mixer call. Going audible
    starts nothing already under way.

    Args:
        audible: True to hear the context's sound, False to keep it off the mixer.

    """
    route = current_context().value(slot=AUDIO_ROUTE_SLOT)
    if route.audible and not audible:
        # Imported here: the audio engine imports the voice table, which imports this module
        from glitchygames.audio.engine import existing_audio_engine
        from glitchygames.audio.voices import stop_plain_plays_and_mute_the_live_pool

        audio_engine = existing_audio_engine()
        if audio_engine is not None:
            audio_engine.fade_out_of_the_mixer()
        stop_plain_plays_and_mute_the_live_pool()
    route.audible = audible
