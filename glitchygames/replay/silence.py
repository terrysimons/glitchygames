"""Run frames in silence: a rebuild's frames and an instant replay's fast-forward.

Frames that run but are not shown (a restarted replay rebuilding up to its pause frame,
glitchygames/replay/rebuild.py; an instant replay fast-forwarding to the seconds it shows,
glitchygames/replay/playback.py) must not be heard either. ``FrameSilencer`` is the one code
path both use:

1. ``begin`` follows the game's own ``pygame.mixer.music.pause()`` and ``unpause()`` calls, so
   music the game paused itself stays paused at the end. With ``spares_playing_sounds`` it also
   notes the sound each busy channel plays then (the live game's, playing on under a scope).
2. ``silence_frame``, after each silent frame, stops every sound the frame started (a channel's
   ``stop()``: ``Sound.play()`` gives its channel full volume again, so lowering volumes would
   not do) and pauses the music. Without ``spares_playing_sounds`` every channel is stopped
   (``pygame.mixer.stop()``, the rebuild's way: nothing of the live game plays under it). With
   it, a channel still playing the sound noted at ``begin`` plays on; a channel that went idle
   or plays another sound loses its note and is stopped. A live voice
   (glitchygames/audio/live.py) queues a new chunk every 100 ms, so its channel soon plays
   another sound and is stopped, as without sparing.
3. ``finish`` stops following the music controls and resumes the music it paused, unless the
   game's last call paused it.

Silencers may stack (a fast-forward inside a rebuild): one pair of wrappers replaces pygame's
``pause`` and ``unpause`` while any silencer follows them. The wrappers tell every following
silencer about the game's call and then call pygame's own functions, captured once when the
first silencer began; the last silencer to stop puts pygame's functions back, provided the
wrappers are still in place (code that replaced them since keeps its own). A silencer's own
pause and resume always call pygame's functions, never the wrappers, so no silencer takes
another's for the game's.

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


class _MusicFollowing:
    """The one pair of music-control wrappers every following silencer shares."""

    def __init__(self: Self) -> None:
        """Start with nothing followed."""
        self.followers: list[FrameSilencer] = []
        # pygame's own pause and unpause, captured when the first follower began
        self.pygame_controls: tuple[Callable[[], None], Callable[[], None]] | None = None
        self.wrappers: tuple[Callable[[], None], Callable[[], None]] | None = None

    def add(self: Self, *, silencer: FrameSilencer) -> None:
        """Follow the game's calls for ``silencer``; the first follower installs the wrappers.

        Args:
            silencer: The silencer beginning.

        """
        self.followers.append(silencer)
        if self.wrappers is not None:
            return
        music = pygame.mixer.music
        self.pygame_controls = (music.pause, music.unpause)
        # The bound methods made once, so the check in remove() finds this very object
        game_pause, game_unpause = self._game_pause, self._game_unpause
        self.wrappers = (game_pause, game_unpause)
        _set_music_controls(pause=game_pause, unpause=game_unpause)

    def remove(self: Self, *, silencer: FrameSilencer) -> None:
        """Stop following for ``silencer``; the last follower puts pygame's functions back.

        Each control only while its wrapper is still in place: a function set over one since is
        kept, and the other control is still given back.

        Args:
            silencer: The silencer stopping.

        """
        if silencer in self.followers:
            self.followers.remove(silencer)
        if self.followers or self.wrappers is None or self.pygame_controls is None:
            return
        pause_wrapper, unpause_wrapper = self.wrappers
        pygame_pause, pygame_unpause = self.pygame_controls
        music = pygame.mixer.music
        _set_music_controls(
            pause=pygame_pause if music.pause is pause_wrapper else music.pause,
            unpause=pygame_unpause if music.unpause is unpause_wrapper else music.unpause,
        )
        self.wrappers = None
        self.pygame_controls = None

    def pygame_pause(self: Self) -> Callable[[], None]:
        """Return pygame's own pause (never a wrapper).

        Returns:
            The function.

        """
        if self.pygame_controls is not None:
            return self.pygame_controls[0]
        return pygame.mixer.music.pause

    def pygame_unpause(self: Self) -> Callable[[], None]:
        """Return pygame's own unpause (never a wrapper).

        Returns:
            The function.

        """
        if self.pygame_controls is not None:
            return self.pygame_controls[1]
        return pygame.mixer.music.unpause

    def _game_pause(self: Self) -> None:
        """The game paused the music: every follower notes it, then pygame pauses."""
        for silencer in self.followers:
            silencer.note_game_music_pause(paused=True)
        self.pygame_pause()()

    def _game_unpause(self: Self) -> None:
        """The game resumed the music: every follower notes it, then pygame resumes."""
        for silencer in self.followers:
            silencer.note_game_music_pause(paused=False)
        self.pygame_unpause()()


def _set_music_controls(*, pause: Callable[[], None], unpause: Callable[[], None]) -> None:
    """Put ``pause`` and ``unpause`` in place of ``pygame.mixer.music``'s.

    Set by name: the type checkers type the module's functions as those exact functions.

    Args:
        pause: The function ``pygame.mixer.music.pause`` is to be.
        unpause: The function ``pygame.mixer.music.unpause`` is to be.

    """
    for name, function in (('pause', pause), ('unpause', unpause)):
        setattr(pygame.mixer.music, name, function)


_MUSIC_FOLLOWING = _MusicFollowing()


class FrameSilencer:
    """Keeps frames silent while they run unseen (see the module docstring)."""

    def __init__(self: Self, *, spares_playing_sounds: bool = False) -> None:
        """Start with nothing silenced and the game's music controls not followed.

        Args:
            spares_playing_sounds: True to let the sounds playing at ``begin`` play on (an
                instant replay's fast-forward); False to stop every sound (a rebuild).

        """
        self.spares_playing_sounds = spares_playing_sounds
        # True while music is paused by the silencer (silence_frame), not by the game
        self._paused_music = False
        # Whether the game's last music.pause() / unpause() call while followed paused it
        self._game_paused_music = False
        self._is_following_music = False
        # Channel index -> the sound it played at begin (spares_playing_sounds)
        self._spared_sounds: dict[int, pygame.mixer.Sound] = {}

    def begin(self: Self) -> None:
        """Follow the game's music controls; note the sounds playing (``spares_playing_sounds``).

        Until ``finish`` (or ``stop_following_music``), the game's ``pause`` and ``unpause``
        calls are noted, so ``finish`` resumes music only when the game did not pause it
        itself. A game that bound the functions before (``from pygame.mixer.music import
        pause``) is not followed. Again: nothing.
        """
        if self._is_following_music:
            return
        self._is_following_music = True
        _MUSIC_FOLLOWING.add(silencer=self)
        if self.spares_playing_sounds and pygame.mixer.get_init() is not None:
            for channel_index in range(pygame.mixer.get_num_channels()):
                playing_sound = pygame.mixer.Channel(channel_index).get_sound()
                if playing_sound is not None:
                    self._spared_sounds[channel_index] = playing_sound

    def note_game_music_pause(self: Self, *, paused: bool) -> None:
        """Note the game's own music pause (True) or resume (False), while followed.

        Args:
            paused: Whether the game's call paused the music.

        """
        self._game_paused_music = paused

    def stop_following_music(self: Self) -> None:
        """Stop following the game's music controls (``begin``)."""
        if not self._is_following_music:
            return
        self._is_following_music = False
        _MUSIC_FOLLOWING.remove(silencer=self)

    def silence_frame(self: Self) -> None:
        """Stop every sound the silent frame just run started, and pause any music.

        Music the silencer paused plays on at ``finish``. Nothing happens without a mixer.
        """
        if pygame.mixer.get_init() is None:
            return
        if self.spares_playing_sounds:
            self._stop_unspared_channels()
        else:
            pygame.mixer.stop()
        if pygame.mixer.music.get_busy():
            # pygame's own pause: the silencer's, not the game's
            _MUSIC_FOLLOWING.pygame_pause()()
            self._paused_music = True

    def _stop_unspared_channels(self: Self) -> None:
        """Stop each busy channel not still playing the sound it played at ``begin``."""
        for channel_index in range(pygame.mixer.get_num_channels()):
            channel = pygame.mixer.Channel(channel_index)
            spared_sound = self._spared_sounds.get(channel_index)
            if not channel.get_busy():
                self._spared_sounds.pop(channel_index, None)
            elif spared_sound is None or channel.get_sound() is not spared_sound:
                self._spared_sounds.pop(channel_index, None)
                channel.stop()

    def finish(self: Self) -> None:
        """End the silence: music the silencer paused plays on, unless the game paused it last."""
        self.stop_following_music()
        self._spared_sounds = {}
        if (
            self._paused_music
            and not self._game_paused_music
            and pygame.mixer.get_init() is not None
        ):
            # pygame's own unpause: other silencers still following must not take it for the
            # game's
            _MUSIC_FOLLOWING.pygame_unpause()()
        self._paused_music = False
