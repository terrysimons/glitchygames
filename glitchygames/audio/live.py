"""Real-time synth voices streamed through reserved mixer channels.

pygame has no audio callback, so each voice renders short chunks from the game loop and keeps
one chunk queued behind the one playing (pygame holds one queued Sound per channel). The safety
margin is the rest of the playing chunk minus one device buffer: about 88 ms at 44100 Hz with a
512-sample buffer and 100 ms chunks. A longer frame underruns; the voice restarts next update.

Channel facts this module relies on (pygame-ce 2.5.8): Channel.stop() and Channel.fadeout()
start the queued sound, so fades are rendered into the samples and stop_now() calls stop()
twice; set_reserved(n) reserves channels 0..n-1; set_num_channels(smaller) stops sounds on the
removed channels, so the pool is reserved once at startup and never resized.
"""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING

import numpy as np
import pygame

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

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.audio.recipes import Tremolo

log: logging.Logger = logging.getLogger('game.audio.live')

DEFAULT_CHUNK_DURATION = 0.1
DEFAULT_FADE_OUT = 0.1


def reserve_live_voice_pool(pool_size: int) -> tuple[int, ...]:
    """Reserve channels for live voices; call once at startup before any sound plays.

    Grows the mixer by pool_size channels, then reserves channels 0..pool_size-1. Nothing is
    playing yet, so those channels are idle, and one-shot sounds keep the original count.

    Returns:
        The reserved channel indices (empty without a mixer or with pool_size 0).

    Raises:
        ValueError: If pool_size is negative.

    """
    if pool_size < 0:
        message = f'pool_size must be >= 0, got {pool_size}'
        raise ValueError(message)
    if pool_size == 0 or pygame.mixer.get_init() is None:
        return ()
    original_count = pygame.mixer.get_num_channels()
    pygame.mixer.set_num_channels(original_count + pool_size)
    reserved_count = pygame.mixer.set_reserved(pool_size)
    return tuple(range(reserved_count))


class VoiceState(enum.Enum):
    """Lifecycle of a live voice."""

    IDLE = 'idle'
    PLAYING = 'playing'
    PAUSED = 'paused'
    FADING = 'fading'
    DRAINING = 'draining'
    STOPPED = 'stopped'


class LiveVoice:
    """An oscillator whose parameters can change every frame."""

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
        """Create a stopped voice; channel None makes a silent no-op voice."""
        self._channel = channel
        self.owner = owner
        self._waveform = waveform
        self._sample_rate = sample_rate
        self._chunk_samples = sample_count(chunk_duration, sample_rate)
        self._random_source = random_source or np.random.default_rng()
        self._target_frequency = frequency
        self._rendered_frequency = frequency
        self._target_volume = volume
        self._rendered_volume = volume
        self._target_cutoff = low_pass_cutoff
        self._rendered_cutoff = low_pass_cutoff
        self._tremolo = tremolo
        self._oscillator_phase = 0.0
        self._tremolo_phase = 0.0
        self._filter_history = np.zeros(DEFAULT_FILTER_TAPS - 1)
        self._fade_total_samples = 0
        self._fade_remaining_samples = 0
        self._state = VoiceState.IDLE

    # --- Parameters (ignored once the voice is stopping or stopped) ---

    @property
    def frequency(self) -> float:
        """Target frequency in Hz."""
        return self._target_frequency

    @frequency.setter
    def frequency(self, value: float) -> None:
        if self._accepts_changes:
            self._target_frequency = value

    @property
    def volume(self) -> float:
        """Target volume 0.0-1.0."""
        return self._target_volume

    @volume.setter
    def volume(self, value: float) -> None:
        if self._accepts_changes:
            self._target_volume = value

    @property
    def low_pass_cutoff(self) -> float | None:
        """Target low-pass cutoff in Hz (None: unfiltered)."""
        return self._target_cutoff

    @low_pass_cutoff.setter
    def low_pass_cutoff(self, value: float | None) -> None:
        if self._accepts_changes:
            self._target_cutoff = value

    @property
    def tremolo(self) -> Tremolo | None:
        """Tremolo settings (None: off)."""
        return self._tremolo

    @tremolo.setter
    def tremolo(self, value: Tremolo | None) -> None:
        if self._accepts_changes:
            self._tremolo = value

    @property
    def _accepts_changes(self) -> bool:
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

    # --- Lifecycle ---

    def start(self) -> None:
        """Start playing (renders and plays the first chunk)."""
        if self._channel is None or self._state is not VoiceState.IDLE:
            return
        self._state = VoiceState.PLAYING
        self._channel.play(to_sound(self._render_chunk(), volume=1.0))

    def update(self) -> None:
        """Keep one chunk queued; call once per frame."""
        if self._channel is None or self._state not in {VoiceState.PLAYING, VoiceState.FADING}:
            return
        if not self._channel.get_busy():
            log.debug('Live voice underrun; restarting')
            self._channel.play(to_sound(self._render_chunk(), volume=1.0))
            return
        if self._channel.get_queue() is None:
            self._channel.queue(to_sound(self._render_chunk(), volume=1.0))

    def stop(self, *, fade_out: float = DEFAULT_FADE_OUT) -> None:
        """Fade to silence over fade_out seconds of rendered audio, then drain."""
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

    # --- Rendering ---

    def _render_chunk(self) -> FloatArray:
        count = self._chunk_samples
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
        samples = self._filtered(raw=raw, ramp=ramp)
        self._filter_history = np.concatenate((self._filter_history, raw))[
            -(DEFAULT_FILTER_TAPS - 1) :
        ]
        if self._tremolo is not None:
            samples, self._tremolo_phase = tremolo(
                samples,
                self._tremolo.rate_hz,
                self._tremolo.depth,
                sample_rate=self._sample_rate,
                phase=self._tremolo_phase,
            )
        samples *= volumes
        if self._state is VoiceState.FADING:
            samples *= self._fade_gains(count)
        return samples

    def _filtered(self, *, raw: FloatArray, ramp: FloatArray) -> FloatArray:
        """Apply the low-pass, crossfading old and new outputs when the cutoff changes.

        Returns:
            The filtered chunk.

        """
        old_output = self._apply_cutoff(raw=raw, cutoff=self._rendered_cutoff)
        if self._target_cutoff == self._rendered_cutoff:
            return old_output
        new_output = self._apply_cutoff(raw=raw, cutoff=self._target_cutoff)
        self._rendered_cutoff = self._target_cutoff
        return old_output * (1.0 - ramp) + new_output * ramp

    def _apply_cutoff(self, *, raw: FloatArray, cutoff: float | None) -> FloatArray:
        if cutoff is None:
            return raw
        kernel = filter_kernel(
            cutoff,
            sample_rate=self._sample_rate,
            taps=DEFAULT_FILTER_TAPS,
            high_pass=False,
        )
        return apply_kernel(raw, kernel, history=self._filter_history)

    def _fade_gains(self, count: int) -> FloatArray:
        positions = self._fade_remaining_samples - np.arange(1, count + 1)
        gains = np.clip(positions / self._fade_total_samples, 0.0, 1.0)
        self._fade_remaining_samples -= count
        if self._fade_remaining_samples <= 0:
            self._state = VoiceState.DRAINING
        return gains


class LiveAudio:
    """Owns the live voice pool and applies the owner rules every frame."""

    def __init__(self, *, channel_indices: Sequence[int]) -> None:
        """Use the channels reserved by reserve_live_voice_pool()."""
        self._pool_size = len(channel_indices)
        self._free_channel_indices = list(channel_indices)
        self._voice_channels: dict[int, int] = {}  # id(voice) -> channel index
        self._voices: list[LiveVoice] = []
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

        Without a mixer the voice is a silent no-op (logged once).

        Returns:
            The voice; call start() to hear it.

        Raises:
            ValueError: If every pool channel is in use.

        """
        if pygame.mixer.get_init() is None:
            if not self._unavailable_logged:
                log.warning('Audio unavailable; live voices are silent')
                self._unavailable_logged = True
            return LiveVoice(
                channel=None,
                owner=owner,
                waveform=waveform,
                frequency=frequency,
                volume=volume,
                low_pass_cutoff=low_pass_cutoff,
                tremolo=tremolo,
                chunk_duration=chunk_duration,
                sample_rate=mixer_sample_rate(),
            )
        if not self._free_channel_indices:
            message = (
                f'All {self._pool_size} live voice channels are in use; raise --live-voice-pool'
            )
            raise ValueError(message)
        channel_index = self._free_channel_indices.pop(0)
        voice = LiveVoice(
            channel=pygame.mixer.Channel(channel_index),
            owner=owner,
            waveform=waveform,
            frequency=frequency,
            volume=volume,
            low_pass_cutoff=low_pass_cutoff,
            tremolo=tremolo,
            chunk_duration=chunk_duration,
            sample_rate=mixer_sample_rate(),
        )
        self._voice_channels[id(voice)] = channel_index
        self._voices.append(voice)
        return voice

    def release_voice(self, voice: LiveVoice) -> None:
        """Silence a voice and return its channel to the pool."""
        voice.stop_now()
        if voice in self._voices:
            self._voices.remove(voice)
            self._free_channel_indices.append(self._voice_channels.pop(id(voice)))

    def update(
        self,
        *,
        active_scene: object | None,
        previous_scene: object | None,
        active_transitions: Sequence[object | None],
    ) -> None:
        """Play voices of active owners, pause the paused scene's, release the rest.

        Args:
            active_scene: SceneManager.active_scene.
            previous_scene: SceneManager.previous_scene (what a PauseScene returns to).
            active_transitions: The running transition and the pending one (either may be
                None); a voice created for a ride is owned by its transition.

        """
        live_transitions = [transition for transition in active_transitions if transition]
        for voice in list(self._voices):
            owner = voice.owner
            owner_is_live_transition = any(
                owner is live_transition for live_transition in live_transitions
            )
            if owner is active_scene or owner_is_live_transition:
                voice.resume()
                voice.update()
            elif owner is previous_scene:
                voice.pause()
            else:
                self.release_voice(voice)
