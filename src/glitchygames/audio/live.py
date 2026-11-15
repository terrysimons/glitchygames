"""Real-time synth voices streamed through reserved mixer channels.

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
    Waveform,
    apply_kernel,
    filter_kernel,
    mixer_sample_rate,
    oscillator,
    sample_count,
    to_sound,
    tremolo,
)
from glitchygames.audio.voices import (
    InnerGameChannelsError,
    inner_game_channels_declared,
    reserve_channels,
    reserved_channel_count,
)
from glitchygames.engine_context import current_context
from glitchygames.randomness import numpy_stream
from glitchygames.render_target import is_inner_context

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from glitchygames.audio.effects import Tremolo
    from glitchygames.audio.instrument import Instrument
    from glitchygames.audio.live_instrument import InstrumentVoice

log: logging.Logger = logging.getLogger('game.audio.live')

DEFAULT_CHUNK_DURATION = 0.1
# The engine numpy stream a voice's noise comes from when none is given (glitchygames/randomness.py)
LIVE_RANDOM_STREAM = 'audio.live'
DEFAULT_FADE_OUT = 0.1


def reserve_live_voice_pool(pool_size: int) -> tuple[int, ...]:
    """Reserve channels for live voices; call once at startup before any sound plays.

    Grows the mixer by pool_size channels, then reserves channels 0..pool_size-1. Nothing is
    playing yet, so those channels are idle, and one-shot sounds keep the original count. A
    wrapper over ``voices.reserve_channels`` (no library channels) until the engine reserves
    the whole partition itself (impl spec 7.1; removed in M2).

    It is the outer game's before any inner game: an inner context's live voices use the live
    pool its engine took, and once inner games' channels are declared the legacy count it
    would pass on counts them, so both are refused.

    Returns:
        The reserved channel indices (empty without a mixer or with pool_size 0).

    Raises:
        ValueError: If pool_size is negative.
        InnerGameChannelsError: In an inner context, or with inner games' channels declared.

    """
    if pool_size < 0:
        message = f'pool_size must be >= 0, got {pool_size}'
        raise ValueError(message)
    if is_inner_context() or inner_game_channels_declared():
        message = (
            'reserve_live_voice_pool is for an outer game before it declares inner games: an '
            "inner game's live voices use the live pool its engine took"
        )
        raise InnerGameChannelsError(message)
    if pool_size == 0 or pygame.mixer.get_init() is None:
        return ()
    # A second engine in one process (a test run, a launcher) finds the pool it grew already
    # there: growing again would add channels per engine, and every set_num_channels reallocates
    # pygame's channel table while the audio thread may still finish a sound on it (BUGS.md
    # #145). So when a partition (this pool's, or reserve_channels' with library channels)
    # already reserves at least the pool, every reserved channel stays reserved and nothing
    # grows: lowering the reservation would hand the library's channels to Sound.play(). A
    # restarted mixer has no partition, so it grows again.
    channel_count = pygame.mixer.get_num_channels()
    already_reserved = reserved_channel_count()
    if already_reserved >= pool_size:
        library_channels = already_reserved - pool_size
        legacy_channels = channel_count - already_reserved
    else:
        library_channels = 0
        legacy_channels = channel_count
    partition = reserve_channels(
        live_pool=pool_size, library_channels=library_channels, legacy_channels=legacy_channels
    )
    return partition.live


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

    Every live voice has one (``LiveVoice``, ``live_instrument.InstrumentVoice``): it asks its
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

    def stop(self, *, fade_out: float = DEFAULT_FADE_OUT) -> None:
        """Fade to silence over fade_out seconds of rendered audio, then drain.

        LiveAudio.update() keeps rendering the fade and returns the channel to the pool once
        the voice has drained.
        """
        if self._channel is None or self._state not in {VoiceState.PLAYING, VoiceState.PAUSED}:
            return
        if self._state is VoiceState.PAUSED:
            self._channel.unpause()
        self._fade_total_samples = max(1, sample_count(fade_out, self._sample_rate))
        self._fade_remaining_samples = self._fade_total_samples
        self._state = VoiceState.FADING

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


class LiveVoice:
    """An oscillator whose parameters can change every frame (the older live API, until M2's end).

    Its rendering is its own; its channel and lifecycle are its ``stream``'s.
    """

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        *,
        channel: pygame.mixer.Channel | None,
        owner: object,
        waveform: Waveform,
        frequency: float,
        volume: float,
        low_pass_cutoff: float | None = None,
        tremolo: Tremolo | None = None,
        chunk_duration: float = DEFAULT_CHUNK_DURATION,
        sample_rate: int,
        random_source: np.random.Generator | None = None,
    ) -> None:
        """Create a stopped voice; channel None makes a silent no-op voice.

        The voice belongs to the current engine context: its route decides each chunk's volume
        (the module docstring).
        """
        self.stream = LiveStream(
            channel=channel,
            owner=owner,
            render=self._render_chunk,
            chunk_samples=sample_count(chunk_duration, sample_rate),
            sample_rate=sample_rate,
        )
        self._waveform = waveform
        self._sample_rate = sample_rate
        self._random_source = (
            random_source if random_source is not None else numpy_stream(LIVE_RANDOM_STREAM)
        )
        self._target_frequency = frequency
        self._rendered_frequency = frequency
        self._target_volume = volume
        self._rendered_volume = volume
        self._target_cutoff = low_pass_cutoff
        self._filter = FilterState(cutoff=low_pass_cutoff, high_pass=False, sample_rate=sample_rate)
        self._tremolo = tremolo
        self._oscillator_phase = 0.0
        self._tremolo_phase = 0.0

    # --- Parameters (ignored once the voice is stopping or stopped) ---

    @property
    def owner(self) -> object:
        """The scene or transition whose life the voice follows."""
        return self.stream.owner

    @owner.setter
    def owner(self, value: object) -> None:
        self.stream.owner = value

    @property
    def frequency(self) -> float:
        """Target frequency in Hz."""
        return self._target_frequency

    @frequency.setter
    def frequency(self, value: float) -> None:
        if self.stream.accepts_changes:
            self._target_frequency = value

    @property
    def volume(self) -> float:
        """Target volume 0.0-1.0."""
        return self._target_volume

    @volume.setter
    def volume(self, value: float) -> None:
        if self.stream.accepts_changes:
            self._target_volume = value

    @property
    def low_pass_cutoff(self) -> float | None:
        """Target low-pass cutoff in Hz (None: unfiltered)."""
        return self._target_cutoff

    @low_pass_cutoff.setter
    def low_pass_cutoff(self, value: float | None) -> None:
        if self.stream.accepts_changes:
            self._target_cutoff = value

    @property
    def tremolo(self) -> Tremolo | None:
        """Tremolo settings (None: off)."""
        return self._tremolo

    @tremolo.setter
    def tremolo(self, value: Tremolo | None) -> None:
        if self.stream.accepts_changes:
            self._tremolo = value

    # --- Lifecycle (the stream's) ---

    @property
    def state(self) -> VoiceState:
        """Current lifecycle state."""
        return self.stream.state

    @property
    def is_playing(self) -> bool:
        """True from start() until the channel has drained (paused counts as playing)."""
        return self.stream.is_playing

    @property
    def is_finished(self) -> bool:
        """True once the voice was stopped, or has faded out and its channel has drained."""
        return self.stream.is_finished

    def start(self) -> None:
        """Start playing (renders and plays the first chunk)."""
        self.stream.start()

    def update(self) -> None:
        """Keep one chunk queued; call once per frame."""
        self.stream.update()

    def stop(self, *, fade_out: float = DEFAULT_FADE_OUT) -> None:
        """Fade to silence over fade_out seconds of rendered audio, then drain."""
        self.stream.stop(fade_out=fade_out)

    def stop_now(self) -> None:
        """Silence immediately."""
        self.stream.stop_now()

    def pause(self) -> None:
        """Pause; the queued chunk is kept."""
        self.stream.pause()

    def resume(self) -> None:
        """Resume after pause()."""
        self.stream.resume()

    # --- Rendering ---

    def _render_chunk(self, count: int) -> FloatArray:
        ramp = np.arange(1, count + 1) / count  # Reaches the target on the last sample
        frequencies = (
            self._rendered_frequency + (self._target_frequency - self._rendered_frequency) * ramp
        )
        volumes = self._rendered_volume + (self._target_volume - self._rendered_volume) * ramp
        self._rendered_frequency = self._target_frequency
        self._rendered_volume = self._target_volume

        raw, self._oscillator_phase = oscillator(
            self._waveform,
            frequencies,
            count / self._sample_rate,
            sample_rate=self._sample_rate,
            phase=self._oscillator_phase,
            random_source=self._random_source,
        )
        samples = self._filter.filtered(raw=raw, ramp=ramp, cutoff=self._target_cutoff)
        if self._tremolo is not None:
            samples, self._tremolo_phase = tremolo(
                samples,
                self._tremolo.rate_hz,
                self._tremolo.depth,
                sample_rate=self._sample_rate,
                phase=self._tremolo_phase,
            )
        samples *= volumes
        return samples


class LiveAudio:
    """Owns the live voice pool and applies the owner rules every frame, to voices' streams."""

    def __init__(self, *, channel_indices: Sequence[int]) -> None:
        """Use the channels reserved by reserve_live_voice_pool()."""
        self._pool_size = len(channel_indices)
        self._free_channel_indices = list(channel_indices)
        self._stream_channels: dict[int, int] = {}  # id(stream) -> channel index
        self._streams: list[LiveStream] = []
        self._unavailable_logged = False

    def create_voice(  # ruff: ignore[too-many-arguments]
        self,
        *,
        owner: object,
        waveform: Waveform,
        frequency: float,
        volume: float = 0.5,
        low_pass_cutoff: float | None = None,
        tremolo: Tremolo | None = None,
        chunk_duration: float = DEFAULT_CHUNK_DURATION,
    ) -> LiveVoice:
        """Create a stopped voice on a free pool channel.

        Without a mixer the voice is a silent no-op (logged once). The channel returns to the
        pool once the voice has drained or been stopped (see update()). Every pool channel in
        use is ``take_channel``'s ValueError.

        Returns:
            The voice; call start() to hear it.

        """
        channel = self.take_channel()
        voice = LiveVoice(
            channel=channel,
            owner=owner,
            waveform=waveform,
            frequency=frequency,
            volume=volume,
            low_pass_cutoff=low_pass_cutoff,
            tremolo=tremolo,
            chunk_duration=chunk_duration,
            sample_rate=mixer_sample_rate(),
        )
        self.track(voice.stream)
        return voice

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
