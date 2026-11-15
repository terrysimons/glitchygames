"""Real-time synth voices streamed through reserved mixer channels: their channel and lifecycle.

Every live voice is a live instrument's (``live_instrument.InstrumentVoice``, started by
``Sound.start()``). This module is the machinery under it: ``LiveStream`` (a voice's channel,
chunks and lifecycle), ``FilterState`` (its low-pass or high-pass, crossfaded across a cutoff
change) and ``LiveAudio`` (a context's live pool and its owner rules). The older
``LiveVoice``, ``LiveAudio.create_voice`` and ``reserve_live_voice_pool`` were removed in sound
migration step 7 (plans/2026-11-14-sound-migration.md).

pygame has no audio callback, so each voice renders short chunks from the game loop and keeps
one chunk queued behind the one playing (pygame holds one queued Sound per channel). The safety
margin is the rest of the playing chunk minus one device buffer: about 88 ms at 44100 Hz with a
512-sample buffer and 100 ms chunks. A longer frame underruns; the voice restarts next update.

Channel facts this module relies on (pygame-ce 2.5.8): Channel.stop() and Channel.fadeout()
start the queued sound, so fades are rendered into the samples and stop_now() calls stop()
twice; set_reserved(n) reserves channels 0..n-1; set_num_channels(smaller) stops sounds on the
removed channels, so the pool is reserved once at startup and never resized.

An inner context's pool is the live pool its build took from the channels the host declared
(``voices.inner_context_partition``; Arcade sub-plan 4, decision 4), never the default
context's. A voice belongs to the context it is
created in: while that context is silent (``glitchygames.audio.route``) its chunks still play on
its own channel, at volume 0 (the voice's lifecycle reads its channel's busy and queue state, so
it is the same heard or silent); each chunk takes the route as it is rendered, so a context
switched audible is heard from its next chunk.
"""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING, Protocol

import numpy as np
import pygame

from glitchygames.audio.route import AUDIO_ROUTE_SLOT
from glitchygames.audio.synth import (
    DEFAULT_FILTER_TAPS,
    FloatArray,
    apply_kernel,
    filter_kernel,
    mixer_sample_rate,
    sample_count,
    to_sound,
)
from glitchygames.engine_context import current_context

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from glitchygames.audio.instrument import Instrument
    from glitchygames.audio.live_instrument import InstrumentVoice

log: logging.Logger = logging.getLogger('game.audio.live')

DEFAULT_CHUNK_DURATION = 0.1
# The engine numpy stream a voice's noise comes from when none is given (glitchygames/randomness.py)
LIVE_RANDOM_STREAM = 'audio.live'
DEFAULT_FADE_OUT = 0.1


class VoiceState(enum.Enum):
    """Lifecycle of a live voice."""

    IDLE = 'idle'
    PLAYING = 'playing'
    PAUSED = 'paused'
    FADING = 'fading'
    DRAINING = 'draining'
    STOPPED = 'stopped'


class LiveStream:
    """A live voice's channel and lifecycle: one chunk playing, one queued, fades rendered in.

    Every live voice (``live_instrument.InstrumentVoice``) has one: it asks its
    voice's ``render`` for each chunk's samples, applies a stopping fade, and plays them at the
    volume the voice's context's route gives (the module docstring). The pool (``LiveAudio``)
    applies the owner rules to streams. A stream without a channel (no mixer) does nothing.
    """

    def __init__(
        self,
        *,
        channel: pygame.mixer.Channel | None,
        owner: object,
        render: Callable[[int], FloatArray],
        chunk_samples: int,
        sample_rate: int,
    ) -> None:
        """Make a stopped stream in the current engine context.

        Args:
            channel: Its pool channel, or None for a silent no-op stream.
            owner: The scene or transition whose life it follows (``LiveAudio.update``).
            render: Renders the next chunk's samples, given their count.
            chunk_samples: Samples per chunk.
            sample_rate: The mixer's rate.
        """
        self._channel = channel
        self._audio_route = current_context().value(slot=AUDIO_ROUTE_SLOT)
        self.owner = owner
        self._render = render
        self._chunk_samples = chunk_samples
        self._sample_rate = sample_rate
        self._fade_total_samples = 0
        self._fade_remaining_samples = 0
        self._state = VoiceState.IDLE

    @property
    def channel(self) -> pygame.mixer.Channel | None:
        """Its pool channel, or None for a silent no-op stream."""
        return self._channel

    @property
    def accepts_changes(self) -> bool:
        """Whether its voice still takes new settings (not once stopping or stopped)."""
        return self._state in {VoiceState.IDLE, VoiceState.PLAYING, VoiceState.PAUSED}

    @property
    def state(self) -> VoiceState:
        """Current lifecycle state."""
        return self._state

    @property
    def is_playing(self) -> bool:
        """True from start() until the channel has drained (paused counts as playing)."""
        if self._channel is None:
            return False
        if self._state in {VoiceState.PLAYING, VoiceState.PAUSED, VoiceState.FADING}:
            return True
        return self._state is VoiceState.DRAINING and bool(self._channel.get_busy())

    @property
    def is_finished(self) -> bool:
        """True once the voice was stopped, or has faded out and its channel has drained."""
        if self._state is VoiceState.STOPPED:
            return True
        return (
            self._state is VoiceState.DRAINING
            and self._channel is not None
            and not self._channel.get_busy()
        )

    def start(self) -> None:
        """Start playing (renders and plays the first chunk)."""
        if self._channel is None or self._state is not VoiceState.IDLE:
            return
        self._state = VoiceState.PLAYING
        self._channel.play(self._next_chunk())

    def update(self) -> None:
        """Keep one chunk queued; call once per frame."""
        if self._channel is None or self._state not in {VoiceState.PLAYING, VoiceState.FADING}:
            return
        if not self._channel.get_busy():
            log.debug('Live voice underrun; restarting')
            self._channel.play(self._next_chunk())
            return
        if self._channel.get_queue() is None:
            self._channel.queue(self._next_chunk())

    def stop(self, *, fade_out: float = DEFAULT_FADE_OUT) -> bool:
        """Fade to silence over fade_out seconds of rendered audio, then drain.

        LiveAudio.update() keeps rendering the fade and returns the channel to the pool once
        the voice has drained.

        Returns:
            Whether the fade began (False once stopping or stopped, or before start()).
        """
        if self._channel is None or self._state not in {VoiceState.PLAYING, VoiceState.PAUSED}:
            return False
        if self._state is VoiceState.PAUSED:
            self._channel.unpause()
        self._fade_total_samples = max(1, sample_count(fade_out, self._sample_rate))
        self._fade_remaining_samples = self._fade_total_samples
        self._state = VoiceState.FADING
        return True

    def stop_now(self) -> None:
        """Silence immediately: the first stop() starts the queued chunk, the second stops it."""
        if self._channel is not None and self._state is not VoiceState.STOPPED:
            self._channel.stop()
            self._channel.stop()
        self._state = VoiceState.STOPPED

    def pause(self) -> None:
        """Pause; the queued chunk is kept."""
        if self._channel is not None and self._state is VoiceState.PLAYING:
            self._channel.pause()
            self._state = VoiceState.PAUSED

    def resume(self) -> None:
        """Resume after pause()."""
        if self._channel is not None and self._state is VoiceState.PAUSED:
            self._channel.unpause()
            self._state = VoiceState.PLAYING

    def _next_chunk(self) -> pygame.mixer.Sound:
        """Render the next chunk, faded while stopping, at the route's volume.

        Returns:
            The chunk as a mixer sound.
        """
        samples = self._render(self._chunk_samples)
        if self._state is VoiceState.FADING:
            samples *= self._fade_gains(self._chunk_samples)
        return to_sound(samples, volume=1.0 if self._audio_route.audible else 0.0)

    def _fade_gains(self, count: int) -> FloatArray:
        positions = self._fade_remaining_samples - np.arange(1, count + 1)
        gains = np.clip(positions / self._fade_total_samples, 0.0, 1.0)
        self._fade_remaining_samples -= count
        if self._fade_remaining_samples <= 0:
            self._state = VoiceState.DRAINING
        return gains


class FilterState:
    """A live voice's low-pass or high-pass: its history, and a cutoff change crossfaded.

    A cutoff change takes effect over one chunk: the chunk is filtered at the old and the new
    cutoff and crossfaded along the chunk's ramp, so it never clicks. The history is the raw
    (unfiltered) signal, so the FIR filter is continuous across chunks.
    """

    def __init__(self, *, cutoff: float | None, high_pass: bool, sample_rate: int) -> None:
        """Start with no history.

        Args:
            cutoff: The cutoff in hertz, or None for no filter.
            high_pass: A high-pass instead of a low-pass.
            sample_rate: The mixer's rate.
        """
        self.rendered_cutoff = cutoff
        self._high_pass = high_pass
        self._sample_rate = sample_rate
        self._history = np.zeros(DEFAULT_FILTER_TAPS - 1)

    def filtered(self, *, raw: FloatArray, ramp: FloatArray, cutoff: float | None) -> FloatArray:
        """Filter a chunk, moving to ``cutoff`` across it if it changed.

        Returns:
            The filtered chunk.
        """
        old_output = self._apply(raw=raw, cutoff=self.rendered_cutoff)
        if cutoff == self.rendered_cutoff:
            output = old_output
        else:
            new_output = self._apply(raw=raw, cutoff=cutoff)
            self.rendered_cutoff = cutoff
            output = old_output * (1.0 - ramp) + new_output * ramp
        self._history = np.concatenate((self._history, raw))[-(DEFAULT_FILTER_TAPS - 1) :]
        return output

    def _apply(self, *, raw: FloatArray, cutoff: float | None) -> FloatArray:
        if cutoff is None:
            return raw
        kernel = filter_kernel(
            cutoff,
            sample_rate=self._sample_rate,
            taps=DEFAULT_FILTER_TAPS,
            high_pass=self._high_pass,
        )
        return apply_kernel(raw, kernel, history=self._history)


class LiveAudio:
    """Owns the live voice pool and applies the owner rules every frame, to voices' streams."""

    def __init__(self, *, channel_indices: Sequence[int]) -> None:
        """Use the context's live pool (``GameEngine.reserved_channel_partition``'s ``live``)."""
        self._pool_size = len(channel_indices)
        self._free_channel_indices = list(channel_indices)
        self._stream_channels: dict[int, int] = {}  # id(stream) -> channel index
        self._streams: list[LiveStream] = []
        self._unavailable_logged = False

    def create_instrument_voice(  # ruff: ignore[too-many-arguments] - the voice's whole setting
        self,
        *,
        owner: object,
        instrument: Instrument,
        frequency: float,
        volume: float = 1.0,
        parameters: Mapping[str, float] | None = None,
        chunk_duration: float = DEFAULT_CHUNK_DURATION,
    ) -> InstrumentVoice:
        """Create a stopped live instrument voice on a free pool channel (``live_instrument``).

        Without a mixer the voice is silent (logged once). A channel taken for a voice that is
        then refused goes back to the pool.

        Returns:
            The voice; ``voice.stream.start()`` plays it.

        Raises:
            ValueError: Every pool channel is in use (``take_channel``), or the voice refuses
                the instrument (``InstrumentVoice``).
        """
        from glitchygames.audio.live_instrument import InstrumentVoice

        channel = self.take_channel()
        try:
            voice = InstrumentVoice(
                channel=channel,
                owner=owner,
                instrument=instrument,
                frequency=frequency,
                volume=volume,
                parameters=parameters,
                chunk_duration=chunk_duration,
                sample_rate=mixer_sample_rate(),
            )
        except ValueError:
            if channel is not None:
                self._free_channel_indices.insert(0, channel.id)
            raise
        self.track(voice.stream)
        return voice

    def take_channel(self) -> pygame.mixer.Channel | None:
        """Take a free pool channel for a new voice (``track`` its stream next).

        Returns:
            The channel, or None without a mixer (the voice is then silent; logged once).

        Raises:
            ValueError: If every pool channel is in use.
        """
        if pygame.mixer.get_init() is None:
            if not self._unavailable_logged:
                log.warning('Audio unavailable; live voices are silent')
                self._unavailable_logged = True
            return None
        if not self._free_channel_indices:
            message = (
                f'All {self._pool_size} live voice channels are in use; raise --live-voice-pool'
            )
            raise ValueError(message)
        return pygame.mixer.Channel(self._free_channel_indices.pop(0))

    def track(self, stream: LiveStream) -> None:
        """Apply the owner rules to a new voice's stream (a silent one needs none)."""
        channel = stream.channel
        if channel is None:
            return
        self._stream_channels[id(stream)] = channel.id
        self._streams.append(stream)

    @property
    def playing_voice_count(self) -> int:
        """Number of pool voices currently playing (see LiveStream.is_playing)."""
        return sum(1 for stream in self._streams if stream.is_playing)

    def release_voice(self, voice: VoiceWithStream) -> None:
        """Silence a voice and return its channel to the pool."""
        self._release(voice.stream)

    def release_every_voice(self) -> None:
        """Silence every voice and return its channel to the pool (an inner game's finish)."""
        for stream in list(self._streams):
            self._release(stream)

    def _release(self, stream: LiveStream) -> None:
        stream.stop_now()
        if stream in self._streams:
            self._streams.remove(stream)
            self._free_channel_indices.append(self._stream_channels.pop(id(stream)))

    def update(
        self,
        *,
        active_scene: object | None,
        previous_scene: object | None,
        active_transitions: Sequence[object | None],
        paused_owners: Sequence[object] = (),
    ) -> None:
        """Play voices of active owners, pause the paused scenes', release the rest.

        Voices that are stopped, or faded out and drained, give their channel back first. A
        fading or draining voice keeps updating even when its owner is paused: stopping wins
        over pausing, so the fade is rendered instead of cut off.

        Args:
            active_scene: SceneManager.active_scene.
            previous_scene: SceneManager.previous_scene (what a PauseScene returns to).
            active_transitions: The running transition and the pending one (either may be
                None); a voice created for a ride is owned by its transition.
            paused_owners: Other owners whose voices pause rather than end: the live scene a
                playback scope stashed, the scene it returns to and the previous scene as it
                began (the game behind a pause screen; glitchygames/replay/playback.py), so
                their voices play on after it.

        """
        live_transitions = [transition for transition in active_transitions if transition]
        for stream in list(self._streams):
            if stream.is_finished:
                self._release(stream)
                continue
            owner = stream.owner
            owner_is_live_transition = any(
                owner is live_transition for live_transition in live_transitions
            )
            if owner is active_scene or owner_is_live_transition:
                stream.resume()
                stream.update()
            elif owner is previous_scene or any(owner is paused for paused in paused_owners):
                if stream.state in {VoiceState.FADING, VoiceState.DRAINING}:
                    stream.update()
                else:
                    stream.pause()
            else:
                self._release(stream)


class VoiceWithStream(Protocol):
    """A live voice the pool can release: it has a ``LiveStream``."""

    @property
    def stream(self) -> LiveStream:
        """The voice's channel and lifecycle."""
        ...
