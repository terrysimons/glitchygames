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
   or plays another sound loses its note and is stopped. A stop starts a channel's queued sound (a
   live voice's next chunk), so each is made twice. Whether a channel is playing is asked of
   ``live.channel_state``, never of ``Channel.get_busy`` alone: a channel reads idle for a moment
   before its queued sound starts (bugs/2026-11-25-live-sounds-restart-mid-chunk.md). A live voice
   (glitchygames/audio/live.py) queues a new chunk every 100 ms, so its channel soon plays
   another sound and is stopped, as without sparing. Each stop is told to the context's audio
   engine (``AudioEngine.silenced``: one channel, or every channel after ``pygame.mixer.stop()``),
   which marks those channels quiet and nothing more: its voices go on by frame time, so their
   handles' ``is_playing``, their ends and the steals are those of the frames had they been
   heard (sound engine impl spec 7.3). The frames are compared with the recording, so a
   silenced frame must not change what the game sees.
3. ``finish`` stops following the music controls and resumes the music it paused, unless the
   game's last call paused it.

Silencers may stack (a fast-forward inside a rebuild): one pair of wrappers replaces pygame's
``pause`` and ``unpause`` while any silencer follows them. The wrappers tell every following
silencer about the game's call and then call pygame's own functions, captured once when the
first silencer began; the last silencer to stop puts pygame's functions back, provided the
wrappers are still in place (code that replaced them since keeps its own). A silencer's own
pause and resume always call pygame's functions, never the wrappers, so no silencer takes
another's for the game's.

In an inner context (an Arcade tile: glitchygames/render_target.py) the mixer is shared with the
host and the other tiles, so the silencer touches only the context's own channels
(``voices.current_inner_context_channel_indices``: its heard set while it holds one, its live
pool, and the unreserved channels playing the plain plays it started): it never calls
``pygame.mixer.stop()`` (each of its own busy channels is stopped instead, and the audio engine
told of each), never stops the host's or another tile's sound, and leaves ``pygame.mixer.music``
alone (the process's, not the tile's; no game uses it). No inner path reaches a silencer today
(a rebuild is watched only, and no game uses instant replay), so this is a guard.

A game that asks the mixer what is playing (``get_busy``, ``Channel.get_busy``) may get a
different answer during silent frames than when they were recorded; audio is played, never
compared, so a replay is unaffected unless game logic depends on it (which no recording could
replay exactly anyway). The sound library's answers (``SoundHandle.is_playing``) never ask the
mixer, so they stay replay-safe. Nothing happens without a mixer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import pygame

from glitchygames.render_target import is_inner_context

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class _MusicFollowing:
    """The one pair of music-control wrappers every following silencer shares."""

    def __init__(self: Self) -> None:
        """Start with nothing followed."""
        self.followers: list[FrameSilencer] = []
        # pygame's own pause and unpause, captured when the first follower began
        self.pygame_controls: tuple[Callable[[], None], Callable[[], None]] | None = None
        # The last pygame_controls captured, kept after the last follower stops: a wrapper left
        # in place then is replaced by these, never taken for pygame's own (BUGS.md #252)
        self.last_pygame_controls: tuple[Callable[[], None], Callable[[], None]] | None = None
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
        # A wrapper of ours still in place (put back by code that saved music.unpause while the
        # wrappers were installed) is never pygame's own: taken for it, the wrapper would call
        # itself. pygame's own, captured by an earlier following (last_pygame_controls), stand
        # in for it: a wrapper is only ever installed after one was captured
        known_pause, known_unpause = self.last_pygame_controls or (music.pause, music.unpause)
        self.pygame_controls = (
            known_pause if self._is_own_wrapper(music.pause) else music.pause,
            known_unpause if self._is_own_wrapper(music.unpause) else music.unpause,
        )
        self.last_pygame_controls = self.pygame_controls
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
        # A follower: FrameSilencer adds itself once (begin) and removes itself once
        # (stop_following_music), guarded by its _is_following_music flag
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

    def _is_own_wrapper(self: Self, function: Callable[[], None]) -> bool:
        """Return whether ``function`` is one of this following's wrappers (a bound method).

        Returns:
            True for its ``_game_pause`` or ``_game_unpause``, bound to it.

        """
        return getattr(function, '__self__', None) is self and getattr(
            function, '__func__', None
        ) in {_MusicFollowing._game_pause, _MusicFollowing._game_unpause}

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


def _tell_the_audio_engine(*, channel_index: int | None) -> None:
    """Tell the audio engine, if there is one, that a channel (None: every channel) was stopped.

    Args:
        channel_index: The channel stopped, or None after ``pygame.mixer.stop()``.

    """
    # Imported when a frame is silenced: importing the replay package never imports audio
    from glitchygames.audio.engine import existing_audio_engine

    audio_engine = existing_audio_engine()
    if audio_engine is not None:
        audio_engine.silenced(channel_index)


def _channel_indices_to_silence() -> Sequence[int]:
    """The channels a silencer may stop: every one, or an inner context's own only.

    Returns:
        Every channel of the mixer, or in an inner context only its own (the module docstring).

    """
    if is_inner_context():
        # Imported when a frame is silenced: importing the replay package never imports audio
        from glitchygames.audio.voices import current_inner_context_channel_indices

        return current_inner_context_channel_indices()
    return range(pygame.mixer.get_num_channels())


def _is_playing(channel: pygame.mixer.Channel) -> bool:
    """Return whether a sound is playing (or paused) on a channel, or about to start on it.

    Returns:
        True when ``live.channel_state`` finds one playing.

    """
    # Imported when a frame is silenced: importing the replay package never imports audio
    from glitchygames.audio.live import ChannelState, channel_state

    return channel_state(channel) in {ChannelState.PLAYING, ChannelState.QUEUED}


def _stop_with_its_queue(channel: pygame.mixer.Channel) -> None:
    """Stop a channel: the first stop starts its queued sound, the second stops that."""
    channel.stop()
    channel.stop()


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
            for channel_index in _channel_indices_to_silence():
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
        inner = is_inner_context()
        if self.spares_playing_sounds:
            self._stop_unspared_channels()
        elif inner:
            self._stop_own_channels()
        else:
            # Twice: the first starts each channel's queued sound
            pygame.mixer.stop()
            pygame.mixer.stop()
            _tell_the_audio_engine(channel_index=None)
        if not inner and pygame.mixer.music.get_busy():
            # pygame's own pause: the silencer's, not the game's
            _MUSIC_FOLLOWING.pygame_pause()()
            self._paused_music = True

    @staticmethod
    def _stop_own_channels() -> None:
        """Stop each playing channel of the inner context's own (never the host's or another's)."""
        for channel_index in _channel_indices_to_silence():
            channel = pygame.mixer.Channel(channel_index)
            if _is_playing(channel):
                _stop_with_its_queue(channel)
                _tell_the_audio_engine(channel_index=channel_index)

    def _stop_unspared_channels(self: Self) -> None:
        """Stop each playing channel not still playing the sound it played at ``begin``.

        Only the inner context's own channels in an inner context (the module docstring).
        """
        for channel_index in _channel_indices_to_silence():
            channel = pygame.mixer.Channel(channel_index)
            spared_sound = self._spared_sounds.get(channel_index)
            if not _is_playing(channel):
                self._spared_sounds.pop(channel_index, None)
            elif spared_sound is None or channel.get_sound() is not spared_sound:
                self._spared_sounds.pop(channel_index, None)
                _stop_with_its_queue(channel)
                _tell_the_audio_engine(channel_index=channel_index)

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
