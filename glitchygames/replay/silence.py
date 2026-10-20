"""Run frames in silence: a rebuild's frames and an instant replay's fast-forward.

Frames that run but are not shown (a restarted replay rebuilding up to its pause frame,
glitchygames/replay/rebuild.py; an instant replay fast-forwarding to the seconds it shows,
glitchygames/replay/playback.py) must not be heard either. ``FrameSilencer`` is the one code
path both use:

1. ``begin`` follows the game's own ``pygame.mixer.music.pause()`` and ``unpause()`` calls
   (the two module functions are replaced by ones that note the call, then call pygame's), so
   music the game paused itself stays paused at the end.
2. ``silence_frame``, after each silent frame: every sound the frame started is stopped
   (``pygame.mixer.stop()``: ``Sound.play()`` gives its channel full volume again, so lowering
   volumes would not do) and music playing is paused.
3. ``finish`` gives pygame its functions back and resumes the music it paused, unless the
   game's last call paused it.

A game that asks the mixer what is playing (``get_busy``, ``Channel.get_busy``) may get a
different answer during silent frames than when they were recorded; audio is played, never
compared, so a replay is unaffected unless game logic depends on it (which no recording could
replay exactly anyway). Nothing happens without a mixer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import pygame

if TYPE_CHECKING:
    from collections.abc import Callable


def _set_music_controls(*, pause: Callable[[], None], unpause: Callable[[], None]) -> None:
    """Put ``pause`` and ``unpause`` in place of ``pygame.mixer.music``'s (``FrameSilencer.begin``).

    Set by name: the type checkers type the module's functions as those exact functions.

    Args:
        pause: The function ``pygame.mixer.music.pause`` is to be.
        unpause: The function ``pygame.mixer.music.unpause`` is to be.

    """
    for name, function in (('pause', pause), ('unpause', unpause)):
        setattr(pygame.mixer.music, name, function)


class FrameSilencer:
    """Keeps frames silent while they run unseen (see the module docstring)."""

    def __init__(self: Self) -> None:
        """Start with nothing silenced and the game's music controls not followed."""
        # True while music is paused by the silencer (silence_frame), not by the game
        self._paused_music = False
        # The game's own music.pause() and music.unpause() calls while silent: whether its
        # last one paused the music (begin), and pygame's functions while followed
        self._game_paused_music = False
        self._followed_music_controls: tuple[Callable[[], None], Callable[[], None]] | None = None

    def begin(self: Self) -> None:
        """Follow the game's own ``pygame.mixer.music.pause()`` and ``unpause()`` calls.

        Until ``finish`` (or ``stop_following_music``), the two module functions are replaced
        by ones that note the call and then call pygame's, so ``finish`` resumes music only when
        the game did not pause it itself. A game that bound the functions before (``from
        pygame.mixer.music import pause``) is not followed. Again: nothing.
        """
        if self._followed_music_controls is not None:
            return
        music = pygame.mixer.music
        pygame_pause, pygame_unpause = music.pause, music.unpause

        def game_pause() -> None:
            self._game_paused_music = True
            pygame_pause()

        def game_unpause() -> None:
            self._game_paused_music = False
            pygame_unpause()

        self._followed_music_controls = (pygame_pause, pygame_unpause)
        _set_music_controls(pause=game_pause, unpause=game_unpause)

    def stop_following_music(self: Self) -> None:
        """Give ``pygame.mixer.music`` its own pause and unpause back (``begin``)."""
        if self._followed_music_controls is None:
            return
        pygame_pause, pygame_unpause = self._followed_music_controls
        _set_music_controls(pause=pygame_pause, unpause=pygame_unpause)
        self._followed_music_controls = None

    def silence_frame(self: Self) -> None:
        """Stop every sound the silent frame just run started, and pause any music.

        Music the silencer paused plays on at ``finish``. Nothing happens without a mixer.
        """
        if pygame.mixer.get_init() is None:
            return
        pygame.mixer.stop()
        if pygame.mixer.music.get_busy():
            pause = (
                pygame.mixer.music.pause
                if self._followed_music_controls is None
                else self._followed_music_controls[0]
            )
            # pygame's own pause: the silencer's, not the game's
            pause()
            self._paused_music = True

    def finish(self: Self) -> None:
        """End the silence: music the silencer paused plays on, unless the game paused it last."""
        self.stop_following_music()
        if (
            self._paused_music
            and not self._game_paused_music
            and pygame.mixer.get_init() is not None
        ):
            pygame.mixer.music.unpause()
        self._paused_music = False
