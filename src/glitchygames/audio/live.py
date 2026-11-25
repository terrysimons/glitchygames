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
removed channels, so the pool is reserved once at startup and never resized. SDL_mixer
keeps a channel's volume from one sound to the next, but a pan is an effect it removes when the
channel's sound ends: ``set_volume(left, right)`` (a pan, at full volume) reaches only the first
chunk. So a stream's gains are rendered into its chunks, side by side, and its channel is set to
full on both sides before each play, as it may still have a volume or a pan another user left
(bugs/2026-11-25-live-sounds-lose-their-pan.md).

A pan change is ramped across a chunk: the queued one, rewritten in place, so it starts within
one chunk. The rewrite renders nothing again (no noise is drawn) and makes no mixer call that
changes anything. Its samples are made first, and written only if the chunk is still queued;
otherwise the next chunk rendered ramps. What is left is the copy itself: if the chunk starts
between that check and the copy's end, the mixer plays the old version up to where it has got
to, then the new one. Both start at the same gains, so the step is at most the change in gain
times the part of the chunk played by then (one mixer buffer of a 0.1 s chunk: 0.116).

A stream holds its own reference to every chunk it plays or queues until its channel has moved
past it (``LiveStream.held_chunks``), so pygame's channel table never holds a chunk's last
reference. pygame-ce 2.5.8's ``endsound_callback`` drops the playing chunk before it clears the
queue slot; when that drop frees the chunk, ``Mix_FreeChunk`` halts the channel and re-enters the
callback, which releases the queued chunk a second time: the heap is corrupted
(bugs/2026-11-24-pygame-mixer-frees-a-queued-sound-twice.md, docs/quality/upstream_issues.md).
A stream is released when its game ends (``SceneManager.terminate`` releases the live voices),
when the pool steals or ends it, or by ``stop_now``. A stream dropped while still holding chunks
was never released: its finalizer stops the channel if the channel still names one, lets go, and
reports it: to its context's registry (``LIVE_STREAMS_SLOT``, a list no logger level can
filter) and as a logged warning. A finalizer must never raise (an exception in a weakref
callback is only printed). Each context's registry also holds its live streams weakly, so the
test harness can ask it, after every test, for each stream still holding chunks
(``live_streams_holding_chunks``) and fail the test that leaked it (tests/harness.py).

Only this module stores ``pygame.mixer.Channel`` objects, so only its table reads can outlive a
mixer quit or restart (a fresh ``Channel(index)`` checks init and range itself). Every read goes
through ``_channel_table_slots``, and a channel at or past ``get_num_channels()`` (a pool shrunk
or restarted under a stale stream) is silent: nothing is played or queued on it.

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
import weakref
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import numpy as np
import pygame
from pydantic import BaseModel, ConfigDict, Field

from glitchygames.audio.live_controls import (
    DEFAULT_CHUNK_SECONDS,
    MAXIMUM_CHUNK_SECONDS,
    MINIMUM_CHUNK_SECONDS,
)
from glitchygames.audio.route import AUDIO_ROUTE_SLOT
from glitchygames.audio.synth import (
    DEFAULT_FILTER_TAPS,
    FloatArray,
    apply_kernel,
    filter_kernel,
    mixer_sample_rate,
    panned_pcm16,
    sample_count,
    to_sound,
)
from glitchygames.audio.voices import constant_power_gains
from glitchygames.engine_context import ContextSlot, current_context

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from glitchygames.audio.instrument import Instrument
    from glitchygames.audio.live_instrument import InstrumentVoice

log: logging.Logger = logging.getLogger('game.audio.live')

DEFAULT_CHUNK_DURATION = DEFAULT_CHUNK_SECONDS
# The engine numpy stream a voice's noise comes from when none is given (glitchygames/randomness.py)
LIVE_RANDOM_STREAM = 'audio.live'
DEFAULT_FADE_OUT = 0.1
# A live voice's stealing priority when none is given (the baked plays' default)
DEFAULT_LIVE_PRIORITY = 50
PAN_RANGE = (-1.0, 1.0)
# A live channel's gains: full on both sides, its chunks carry their own (the module docstring)
FULL_CHANNEL_GAINS = (1.0, 1.0)
# The most chunks a stream holds once it has let go of those its channel moved past: pygame's
# table names one playing and one queued per channel
MAXIMUM_HELD_CHUNKS = 2
# Logged by a stream's finalizer when it was collected still holding chunks: nobody released it
UNRELEASED_LIVE_STREAM_MESSAGE = (
    'A live stream (%s) was never released: collected holding %d chunk(s) '
    '(release_voice, release_every_voice or stop_now)'
)


class UnreleasedLiveStreamReport(BaseModel):
    """A live stream collected while still holding chunks: nobody released it.

    Attributes:
        stream_name: Its owner's class and its channel (``LiveStream.diagnostic_name``).
        stream_id: The stream's ``id``, for telling which stream a report is about.
        held_chunk_count: How many chunks it still held.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    stream_name: str
    stream_id: int
    held_chunk_count: int


class LiveStreamRegistry:
    """One context's live streams, held weakly, and the reports of those collected unreleased.

    A diagnostic: nothing in a game reads it. The test harness asks it after every test.
    """

    def __init__(self) -> None:
        """Start with no stream and no report."""
        self._streams: weakref.WeakSet[LiveStream] = weakref.WeakSet()
        self._unreleased_reports: list[UnreleasedLiveStreamReport] = []

    def add(self, stream: LiveStream) -> None:
        """Name a new stream (``LiveStream.__init__``)."""
        self._streams.add(stream)

    def streams_holding_chunks(self) -> tuple[LiveStream, ...]:
        """Every stream of this context still alive and holding a chunk, whatever its channel.

        Returns:
            The streams.
        """
        return tuple(stream for stream in self._streams if stream.held_chunks)

    def report_unreleased(self, report: UnreleasedLiveStreamReport) -> None:
        """Keep a collected stream's report (its finalizer, ``_let_go_of_chunks``)."""
        self._unreleased_reports.append(report)

    def take_unreleased_reports(self) -> tuple[UnreleasedLiveStreamReport, ...]:
        """Take the reports kept since they were last taken.

        Returns:
            The reports, oldest first; none are kept.
        """
        reports = tuple(self._unreleased_reports)
        self._unreleased_reports.clear()
        return reports


LIVE_STREAMS_SLOT: ContextSlot[LiveStreamRegistry] = ContextSlot(
    name='glitchygames.audio.live.live_streams', factory=LiveStreamRegistry
)


def live_streams_holding_chunks() -> tuple[LiveStream, ...]:
    """The current context's live streams still holding chunks (a diagnostic).

    Returns:
        The streams.
    """
    return current_context().value(slot=LIVE_STREAMS_SLOT).streams_holding_chunks()


def take_unreleased_live_stream_reports() -> tuple[UnreleasedLiveStreamReport, ...]:
    """Take the current context's reports of live streams collected unreleased (a diagnostic).

    Returns:
        The reports, oldest first.
    """
    return current_context().value(slot=LIVE_STREAMS_SLOT).take_unreleased_reports()


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

    Its chunks are panned by the constant-power law every sound pans by (the owner, 2026-11-15:
    one law, so a live sound centred is as loud as a baked one, and its first pan never jumps),
    each chunk from its first to its last sample; its channel is set to full on both sides before
    each play, so a stream never inherits a pan its channel had and never leaves one. A pan
    change is heard from the start of the next chunk, ramped across it (the module docstring).
    A pause made by ``hold`` holds until
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
        # The newest chunk's samples, and the gains it starts and ends at (None: none rendered)
        self._newest_samples: FloatArray | None = None
        self._newest_starting_gains = self._pan_gains()
        self._newest_ending_gains: tuple[float, float] | None = None
        self._held = False
        # Every chunk played or queued that the channel may still name (the module docstring)
        self._held_chunks: list[pygame.mixer.Sound] = []
        # Read now: Channel.id raises once the mixer has quit
        self._diagnostic_name = (
            f'{type(owner).__qualname__} on channel {"none" if channel is None else channel.id}'
        )
        if channel is not None:
            registry = current_context().value(slot=LIVE_STREAMS_SLOT)
            registry.add(self)
            weakref.finalize(
                self,
                _let_go_of_chunks,
                channel,
                self._held_chunks,
                UnreleasedLiveStreamReport(
                    stream_name=self._diagnostic_name, stream_id=id(self), held_chunk_count=0
                ),
                registry,
            ).atexit = False

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
    def diagnostic_name(self) -> str:
        """Its owner's class and its channel, as reports name it."""
        return self._diagnostic_name

    @property
    def held_chunks(self) -> tuple[pygame.mixer.Sound, ...]:
        """The chunks it holds: every one its channel names, at most ``MAXIMUM_HELD_CHUNKS``."""
        return tuple(self._held_chunks)

    @property
    def is_held(self) -> bool:
        """Whether a pause made by ``hold`` is holding it."""
        return self._held

    def set_pan(self, pan: float) -> None:
        """Pan by the constant-power law, ramped across the next chunk to start.

        That is the chunk queued, rewritten in place, or the next one rendered when none is (or
        when the queued one started meanwhile). The chunk playing plays on as it is: the change
        starts within one chunk (what is left of the race: the module docstring).

        Raises:
            ValueError: For a pan outside -1 to 1.
        """
        if not PAN_RANGE[0] <= pan <= PAN_RANGE[1]:
            message = f'pan must be between -1 and 1, got {pan}'
            raise ValueError(message)
        self._pan = pan
        if self._channel is None or self._newest_samples is None:
            return  # the first chunk starts at the pan
        ending_gains = self._pan_gains()
        if ending_gains == self._newest_ending_gains:
            return  # the newest chunk ends there already
        _, queued = _channel_table_slots(self._channel)
        if queued is None or not self._held_chunks or queued is not self._held_chunks[-1]:
            return  # nothing of its own waits: the next chunk rendered ramps to the pan
        frames = pygame.sndarray.samples(queued)
        panned = panned_pcm16(
            self._newest_samples,
            side_gains=self._side_gains(starting=self._newest_starting_gains, ending=ending_gains),
            channel_count=1 if frames.ndim == 1 else frames.shape[1],
        )
        _, still_queued = _channel_table_slots(self._channel)
        if still_queued is not queued:
            return  # it started meanwhile: the next chunk rendered ramps from what is heard
        self._newest_ending_gains = ending_gains
        frames[...] = panned

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
        if not _channel_in_the_table(self._channel):
            return  # a pool shrunk under it: silent (the module docstring)
        self._play(self._channel)

    def update(self) -> None:
        """Keep one chunk queued, letting go of the chunks played out; call once per frame."""
        if self._channel is None:
            return
        self._let_go_of_chunks_played_out(self._channel)
        if self._state not in {VoiceState.PLAYING, VoiceState.FADING}:
            return
        if not _channel_in_the_table(self._channel):
            return  # a pool shrunk under it: silent (the module docstring)
        if not self._channel.get_busy():
            log.debug('Live voice underrun; restarting')
            self._play(self._channel)
            return
        _, queued = _channel_table_slots(self._channel)
        if queued is None:
            chunk = self._next_chunk()
            self._held_chunks.append(chunk)
            self._channel.queue(chunk)
            self._let_go_of_chunks_played_out(self._channel)

    def stop(self, *, fade_out: float = DEFAULT_FADE_OUT) -> bool:
        """Fade to silence over fade_out seconds of rendered audio, then drain.

        LiveAudio.update() keeps rendering the fade and returns the channel to the pool once
        the voice has drained. The fade starts in the next chunk rendered: the chunk playing
        and the one already queued play out unfaded first, so the fade is heard up to about two
        chunks late (128-198 ms with the default 0.1 s chunks, measured on SDL's disk driver,
        2026-11-21). stop_now() silences at once.

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
            self._let_go_of_chunks_played_out(self._channel)
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

    def _play(self, channel: pygame.mixer.Channel) -> None:
        """Play the next chunk, holding it and every chunk the channel named before the play.

        The channel's gains go to full first: its chunks carry theirs (the module docstring).
        The chunks the channel played before are let go only after ``Channel.play`` has
        replaced them in pygame's table, never inside it (the module docstring). Both callers
        (``start``, ``update``) have checked the channel is in the table: pygame's ``chan_play``
        indexes it with SDL's -1 for a channel SDL refuses.
        """
        chunk = self._next_chunk()
        self._held_chunks.append(chunk)
        channel.set_volume(*FULL_CHANNEL_GAINS)
        channel.play(chunk)
        self._let_go_of_chunks_played_out(channel)

    def _let_go_of_chunks_played_out(self, channel: pygame.mixer.Channel) -> None:
        """Keep only the held chunks the channel still names, playing or queued."""
        named = _channel_table_slots(channel)
        self._held_chunks[:] = [
            chunk for chunk in self._held_chunks if any(chunk is sound for sound in named)
        ]

    def _next_chunk(self) -> pygame.mixer.Sound:
        """Render the next chunk, faded while stopping, at its pan and the route's volume.

        It starts at the gains the chunk before it ended at and ramps to the pan's.

        Returns:
            The chunk as a mixer sound.
        """
        samples = self._render(self._chunk_samples)
        if self._state is VoiceState.FADING:
            samples *= self._fade_gains(self._chunk_samples)
        target = self._pan_gains()
        self._newest_samples = samples
        self._newest_starting_gains = self._newest_ending_gains or target
        self._newest_ending_gains = target
        side_gains = self._side_gains(starting=self._newest_starting_gains, ending=target)
        if not self._audio_route.audible:
            return to_sound(samples, volume=0.0, side_gains=side_gains)
        return to_sound(
            samples,
            volume=1.0 if self._gain_source is None else self._gain_source(),
            side_gains=side_gains,
        )

    def _pan_gains(self) -> tuple[float, float]:
        """The pan's left and right gains, by the constant-power law.

        Returns:
            The gains.
        """
        return constant_power_gains(pan=self._pan, gain=1.0)

    def _side_gains(
        self, *, starting: tuple[float, float], ending: tuple[float, float]
    ) -> FloatArray:
        """Each sample's left and right gain in a chunk: a straight line between its ends.

        Returns:
            (sample count, 2): the first sample has left the starting gains, the last is at the
            ending ones.
        """
        ramp = np.arange(1, self._chunk_samples + 1)[:, np.newaxis] / self._chunk_samples
        return np.array(starting) + (np.array(ending) - np.array(starting)) * ramp

    def _fade_gains(self, count: int) -> FloatArray:
        positions = self._fade_remaining_samples - np.arange(1, count + 1)
        gains = np.clip(positions / self._fade_total_samples, 0.0, 1.0)
        self._fade_remaining_samples -= count
        if self._fade_remaining_samples <= 0:
            self._state = VoiceState.DRAINING
        return gains


def _channel_in_the_table(channel: pygame.mixer.Channel) -> bool:
    """Whether pygame's channel table has this stored channel: the mixer runs, the pool holds it.

    Returns:
        False on a quit mixer, or for a channel at or past ``get_num_channels()``.
    """
    return pygame.mixer.get_init() is not None and channel.id < pygame.mixer.get_num_channels()


def _channel_table_slots(
    channel: pygame.mixer.Channel,
) -> tuple[pygame.mixer.Sound | None, pygame.mixer.Sound | None]:
    """The Sounds pygame's channel table names for a stored channel: playing, then queued.

    pygame-ce 2.5.8's ``Channel.get_sound`` and ``get_queue`` index its table with no check that
    the mixer is running or the channel exists. Only a stored ``Channel`` (this module's) can
    outlive its mixer: on a quit mixer the table is gone (a NULL read), and on a restarted one it
    has 8 entries (a read past its end). Neither names a chunk played before. The table never
    shrinks, so a channel below ``get_num_channels()`` is inside it; one at or past it (the pool
    shrank or the mixer restarted) is not read, and (None, None) is returned.

    Returns:
        The playing and the queued Sound, each None when there is none or it was not read.
    """
    if not _channel_in_the_table(channel):
        return (None, None)
    return (channel.get_sound(), channel.get_queue())


def _let_go_of_chunks(
    channel: pygame.mixer.Channel,
    held_chunks: list[pygame.mixer.Sound],
    report: UnreleasedLiveStreamReport,
    registry: LiveStreamRegistry,
) -> None:
    """Let go of a dropped stream's chunks, stopping its channel first if it still names one.

    A stream's finalizer (``LiveStream.__init__``): it holds the channel, the chunk list, the
    stream's report made at construction (its name: ``Channel.id`` raises on a quit mixer) and
    its context's registry, not the stream. Stopped twice (the module's channel facts),
    pygame's table names none of them, so none is freed inside pygame's callback. A quit or
    restarted mixer names none of them: they simply go, and nothing asks the mixer anything.
    Holding any chunk at all means nobody released the stream, which is reported once it has
    let go: kept in the registry and logged (``UNRELEASED_LIVE_STREAM_MESSAGE``). It never
    raises.
    """
    if not held_chunks:
        return
    named = _channel_table_slots(channel)
    if any(chunk is sound for chunk in held_chunks for sound in named):
        channel.stop()
        channel.stop()
    held_count = len(held_chunks)
    held_chunks.clear()
    registry.report_unreleased(report.model_copy(update={'held_chunk_count': held_count}))
    log.warning(UNRELEASED_LIVE_STREAM_MESSAGE, report.stream_name, held_count)


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
