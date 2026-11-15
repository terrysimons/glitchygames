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
import itertools
import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import numpy as np
import pygame
from pydantic import BaseModel, ConfigDict, Field

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
from glitchygames.audio.voices import constant_power_gains
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
# A start's chunk length (Sound.start(chunk_seconds=)): below 30 ms one chunk cannot cover a
# 60 fps frame plus the 11.6 ms device buffer, so the voice would underrun every frame
MINIMUM_CHUNK_SECONDS = 0.03
MAXIMUM_CHUNK_SECONDS = 0.5
# A live voice's stealing priority when none is given (the baked plays' default)
DEFAULT_LIVE_PRIORITY = 50
PAN_RANGE = (-1.0, 1.0)


@runtime_checkable
class GainSource(Protocol):
    """Gives a live voice's bus gain as each chunk is rendered (``Bus.effective_gain``)."""

    def __call__(self) -> float:
        """The gain, 0 or more."""
        ...


class LiveVoiceOptions(BaseModel):
    """How a live voice plays beside what it plays: ``Sound.start()``'s playback settings.

    Attributes:
        chunk_seconds: Seconds per chunk (the voice's latency), 0.03 to 0.5.
        persist: Outlive its owner; the pause rules still hold (``LiveAudio.update``).
        priority: Its stealing priority: a full pool steals a lower one first.
        pan: -1 (left) to 1 (right), by the constant-power law every sound pans by (centre is
            3 dB down on each side, as a baked play's).
        gain_source: Gives its bus's gain, read as each chunk is rendered; None is 1.0.
    """

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    chunk_seconds: float = Field(
        default=DEFAULT_CHUNK_DURATION, ge=MINIMUM_CHUNK_SECONDS, le=MAXIMUM_CHUNK_SECONDS
    )
    persist: bool = False
    priority: int = DEFAULT_LIVE_PRIORITY
    pan: float = Field(default=0.0, ge=PAN_RANGE[0], le=PAN_RANGE[1])
    gain_source: GainSource | None = None


DEFAULT_LIVE_VOICE_OPTIONS = LiveVoiceOptions()


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
    volume the voice's context's route gives (the module docstring), times its bus's gain read
    as each chunk is rendered. The pool (``LiveAudio``) applies the owner rules to streams. A
    stream without a channel (no mixer) does nothing.

    Its channel pans by the constant-power law every sound pans by (the owner, 2026-11-15: one
    law, so a live sound centred is as loud as a baked one, and its first pan never jumps); it
    sets its channel's pan as it starts, so it never inherits the pan a pool channel had. A
    pause made by ``hold`` holds until
    ``release_hold``: the owner rules never resume it. ``persist`` and ``priority`` are the
    pool's to read (``LiveAudio.update``, ``LiveAudio.take_channel``).
    """

    def __init__(
        self,
        *,
        channel: pygame.mixer.Channel | None,
        owner: object,
        render: Callable[[int], FloatArray],
        sample_rate: int,
        options: LiveVoiceOptions = DEFAULT_LIVE_VOICE_OPTIONS,
    ) -> None:
        """Make a stopped stream in the current engine context.

        Args:
            channel: Its pool channel, or None for a silent no-op stream.
            owner: The scene or transition whose life it follows (``LiveAudio.update``).
            render: Renders the next chunk's samples, given their count.
            sample_rate: The mixer's rate.
            options: Its chunk length, persist, priority, pan and bus gain.
        """
        self._channel = channel
        self._audio_route = current_context().value(slot=AUDIO_ROUTE_SLOT)
        self.owner = owner
        self._render = render
        self._chunk_samples = sample_count(options.chunk_seconds, sample_rate)
        self._sample_rate = sample_rate
        self._fade_total_samples = 0
        self._fade_remaining_samples = 0
        self._state = VoiceState.IDLE
        self.persist = options.persist
        self.priority = options.priority
        self.made_order = 0  # set by the pool: earlier voices are stolen first among equals
        self._gain_source = options.gain_source
        self._pan = options.pan
        self._held = False

    @property
    def chunk_samples(self) -> int:
        """Samples per chunk."""
        return self._chunk_samples

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

    @property
    def is_held(self) -> bool:
        """Whether a pause made by ``hold`` is holding it."""
        return self._held

    def set_pan(self, pan: float) -> None:
        """Pan its channel by the constant-power law.

        Raises:
            ValueError: For a pan outside -1 to 1.
        """
        if not PAN_RANGE[0] <= pan <= PAN_RANGE[1]:
            message = f'pan must be between -1 and 1, got {pan}'
            raise ValueError(message)
        self._pan = pan
        if self._channel is not None:
            self._channel.set_volume(*self._channel_gains())

    def hold(self) -> bool:
        """Pause until ``release_hold``, whatever the owner rules say.

        Returns:
            Whether it was playing and is now held.
        """
        if self._channel is None or self._state is not VoiceState.PLAYING:
            return False
        self.pause()
        self._held = True
        return True

    def release_hold(self) -> bool:
        """End a pause ``hold`` made: it plays on.

        Returns:
            Whether a hold was ended.
        """
        if not self._held:
            return False
        self._held = False
        self.resume()
        return True

    def start(self) -> None:
        """Start playing (renders and plays the first chunk)."""
        if self._channel is None or self._state is not VoiceState.IDLE:
            return
        self._state = VoiceState.PLAYING
        self._channel.set_volume(*self._channel_gains())
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
        self._held = False

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
        if not self._audio_route.audible:
            return to_sound(samples, volume=0.0)
        return to_sound(samples, volume=1.0 if self._gain_source is None else self._gain_source())

    def _channel_gains(self) -> tuple[float, float]:
        """Its channel's left and right gains, by the constant-power law.

        Returns:
            The gains.
        """
        return constant_power_gains(pan=self._pan, gain=1.0)

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
        self._made = itertools.count(1)

    def create_instrument_voice(  # ruff: ignore[too-many-arguments] - the voice's whole setting
        self,
        *,
        owner: object,
        instrument: Instrument,
        frequency: float,
        volume: float = 1.0,
        parameters: Mapping[str, float] | None = None,
        options: LiveVoiceOptions = DEFAULT_LIVE_VOICE_OPTIONS,
    ) -> InstrumentVoice:
        """Create a stopped live instrument voice on a free pool channel (``live_instrument``).

        Without a mixer the voice is silent (logged once). A full pool steals for it
        (``take_channel``). A channel taken for a voice that is then refused goes back to the
        pool. ``options`` are its stream's.

        Returns:
            The voice; ``voice.stream.start()`` plays it.

        Raises:
            ValueError: Every pool channel is in use (``take_channel``), or the voice refuses
                the instrument (``InstrumentVoice``).
        """
        from glitchygames.audio.live_instrument import InstrumentVoice

        channel = self.take_channel(priority=options.priority)
        try:
            voice = InstrumentVoice(
                channel=channel,
                owner=owner,
                instrument=instrument,
                frequency=frequency,
                volume=volume,
                parameters=parameters,
                options=options,
                sample_rate=mixer_sample_rate(),
            )
        except ValueError:
            if channel is not None:
                self._free_channel_indices.insert(0, channel.id)
            raise
        self.track(voice.stream)
        return voice

    def take_channel(self, *, priority: int = DEFAULT_LIVE_PRIORITY) -> pygame.mixer.Channel | None:
        """Take a free pool channel for a new voice (``track`` its stream next).

        A full pool steals: the voice of the lowest priority at or below ``priority`` (the
        earliest made among equals) is cut at once and its channel taken.

        Args:
            priority: The new voice's priority.

        Returns:
            The channel, or None without a mixer (the voice is then silent; logged once).

        Raises:
            ValueError: If every pool channel is in use by voices of a higher priority.
        """
        if pygame.mixer.get_init() is None:
            if not self._unavailable_logged:
                log.warning('Audio unavailable; live voices are silent')
                self._unavailable_logged = True
            return None
        if not self._free_channel_indices:
            stealable = [stream for stream in self._streams if stream.priority <= priority]
            if not stealable:
                message = (
                    f'All {self._pool_size} live voice channels are in use; raise --live-voice-pool'
                )
                raise ValueError(message)
            victim = min(stealable, key=lambda stream: (stream.priority, stream.made_order))
            log.debug('Live voice of priority %d stolen for one of %d', victim.priority, priority)
            self._release(victim)
        return pygame.mixer.Channel(self._free_channel_indices.pop(0))

    def track(self, stream: LiveStream) -> None:
        """Apply the owner rules to a new voice's stream (a silent one needs none)."""
        channel = stream.channel
        if channel is None:
            return
        self._stream_channels[id(stream)] = channel.id
        stream.made_order = next(self._made)
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
        over pausing, so the fade is rendered instead of cut off. A persisting voice whose
        owner is gone plays on instead of being released, and a held one stays paused.

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
                self._play_on(stream)
            elif owner is previous_scene or any(owner is paused for paused in paused_owners):
                if stream.state in {VoiceState.FADING, VoiceState.DRAINING}:
                    stream.update()
                else:
                    stream.pause()
            elif stream.persist:
                self._play_on(stream)
            else:
                self._release(stream)

    @staticmethod
    def _play_on(stream: LiveStream) -> None:
        """Resume a stream the owner rules let play (unless held) and keep a chunk queued."""
        if not stream.is_held:
            stream.resume()
        stream.update()


class VoiceWithStream(Protocol):
    """A live voice the pool can release: it has a ``LiveStream``."""

    @property
    def stream(self) -> LiveStream:
        """The voice's channel and lifecycle."""
        ...
