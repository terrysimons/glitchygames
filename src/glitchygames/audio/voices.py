"""The voice table: library plays on reserved mixer channels (impl spec 4.4 and 7.1-7.3).

The mixer's channels are partitioned once at startup (``reserve_channels``): ``0 .. live-1``
for live voices, the next ``library`` channels for this table, and the rest (pygame's default
8) for legacy ``Sound.play()`` callers, which SDL places only on unreserved channels. The table
never calls ``Sound.play()``, so neither side can cut the other off (AUD-MIX-008).

An inner context (an Arcade tile; Arcade sub-plan 4, decisions 4, 5 and 7) never partitions: it
takes a channel block of its own (``context_channel_block``), its library channels and then its
live pool, sized by its own options (``--sound-channels``, ``--live-voice-pool``), so its steals
and drops are those of the game run alone, and no block shares a channel with the default
context's partition or another block. SDL reserves only a prefix of the channels
(``set_reserved(n)`` reserves ``0 .. n-1``), so the blocks lie right above the default
partition, inside the reservation, which is raised over them; the legacy channels move above
every block, as many as before, so a plain ``Sound.play()`` never lands on a block. Growing the
mixer for a block is the one ``set_num_channels`` after startup (BUGS.md #145: it reallocates
pygame's channel table under the audio thread), so a freed block (``free_context_channel_block``)
is reused by the next one and nothing ever lowers the reservation or shrinks the mixer. A default
partition made while blocks are laid out keeps them reserved, and is refused when its channels
would cover a held block (``ChannelsHeldError``). ``release_channels`` (shutdown) forgets them.

Each library channel is one slot of the table. A play takes the lowest free channel its bus may
use (bus reservations: ``Bus.reserved_channels``), else steals a playing voice of lower or
equal priority (releasing first, then lowest priority, earliest play, lowest channel; decided
from the table alone, so it is deterministic: AUD-MIX-003), else is dropped and counted. A
stolen channel fades with ``Channel.fadeout(10)``; the stealer takes another free channel, or
waits one frame for the stolen one (counted as a delayed play) because ``Channel.play`` on a
fading channel replaces the fading sound at the next mixer chunk, so the fade is never heard
(impl spec 7.1, measured on SDL's disk driver: tests/audio/test_channel_fades.py). SDL_mixer
steps a fade once per chunk (512 frames, 11.6 ms), so even the delayed steal's 10 ms fade is a
plateau or a halt, not a ramp: steals are not yet click-free (impl spec risk R4, **[Open]**).

What the game sees (``SoundHandle.is_playing``, voices ending) follows each voice's
``played_seconds``, which ``advance`` moves by the served frame time only while the voice is not
paused, never ``Channel.get_busy()`` (impl spec 7.3), so a replay sees the same answers. Which
channels are free, and so whether a play steals, is decided by the table alone (ruling R30): a
channel is free once its voice ended by played time, or its stop's fade ran out in frame time.
The device is asked only which free channel to prefer (one no longer sounding), which decides
the channel index a play lands on, never what the game sees. That index is the device's choice,
not an answer: a heard and a silent run of the same plays may put a voice on different channels
(``SoundHandle.slot`` and the debug panel show the one it got). A stopped or cancelled voice's
handle answers ``False`` at once while its channel finishes the fade (ruling R31).

A silenced frame (``FrameSilencer``: a rebuild's or a fast-forward's frames, which are compared
with the recording) stops channels behind the table's back. ``silenced(channel)`` only marks the
slot device-stopped: the voice keeps its generation and its played time, so ``is_playing``, voice
ends and steal decisions are those of the run that was not silenced; only the channel is quiet,
and the table uses it again as usual (impl spec 7.3). Owners are compared by identity, never by
``==`` (scenes are compared as objects, as the audio engine's ``_contains`` does).

Handles are ``(slot, generation)`` values. A slot's generation moves whenever its voice ends,
so a handle whose voice ended, was stolen or was replaced answers ``False`` and never controls
the voice that took its slot later (impl spec 4.4).

``release()`` on a looping voice ends the loop after the current pass: pygame cannot change a
playing channel's loop count, so the channel fades out over what is left of the pass
(``Channel.fadeout``), ending exactly at the pass's end. That pass's remainder is heard fading,
not at full level (a documented simplification; the brief's ruling).

A silent context (``glitchygames.audio.route``; Arcade sub-plan 4, decision 3) keeps its table off
the mixer: a silent tile's sound must not be heard, and its block's channels may be shared with
sounds that are (plain plays from before the block was laid out). The table asks the audio route of
the context it was made in (its audio engine's, made and installed in that context), not the
current one, so a handle used from another context still follows its own context's route. While
that context is silent the table makes no mixer call (``play``, ``fadeout``, ``stop``, ``pause``,
``unpause``, ``set_volume``) and reads every channel as idle (``get_busy`` is never asked): its
voices, their ends, steals, delayed plays and ``is_playing`` go on by frame time exactly as heard,
since none of them was ever decided by the device. Each slot remembers whether its voice (or fade)
reached the mixer (``_Slot.heard``), and only such a slot's channel is touched, and only while the
context is audible.

Going silent is two steps in this order: ``fade_out_of_the_mixer`` (called by the audio engine
while the context is still audible, ``AudioEngine.fade_out_of_the_mixer``) fades every heard
channel over the scene clean-up's 50 ms and marks every slot unheard; then the route turns silent
and the table goes quiet. A paused channel cannot fade and is silent, so it is stopped; so is one
already fading for longer than the 50 ms, because SDL_mixer ignores a ``fadeout`` on a channel
that is already fading out (measured with pygame-ce 2.5.8 on SDL's dummy driver: a 20 ms fadeout
after a 2 s one left the channel busy 0.3 s later), so its fade would go on to its end. A channel
already fading within the 50 ms (a steal's 10 ms, a short stop) is left to finish. Going audible
again starts nothing already under way: a voice is heard only when it starts while its context is
audible.
"""

from __future__ import annotations

import contextlib
import dataclasses
import enum
import itertools
import logging
import math
import operator
from typing import TYPE_CHECKING

import pygame

from glitchygames.audio.route import AUDIO_ROUTE_SLOT
from glitchygames.engine_context import ContextSlot, current_context

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Generator

    from glitchygames.audio.buses import BusTree
    from glitchygames.audio.library import Sound

log: logging.Logger = logging.getLogger('game.audio.voices')

# Impl spec 7.1: a stolen voice fades over 10 ms
STEAL_FADE_MILLISECONDS = 10
# Feature spec, Lifecycle: stop() fades over at least 5 ms; cancel() is a 5 ms de-click
MINIMUM_FADE_SECONDS = 0.005
CANCEL_FADE_SECONDS = 0.005
# Feature spec 7.4: scene clean-up (and shutdown) fade over 50 ms
DEFAULT_STOP_FADE_SECONDS = 0.05
# Frame times are float sums (60 frames of 1/60 s add up to a hair under 1.0), so a voice or a
# fade counts as finished when less than this is left
TIME_TOLERANCE_SECONDS = 1e-9
MINIMUM_PRIORITY = 0
MAXIMUM_PRIORITY = 100
MILLISECONDS_PER_SECOND = 1000

# The last partition's mixer: its channel count afterwards and the channels it reserved, which
# reserved_channel_count reads back
_partitioned_mixer: dict[str, int] = {}


class _ChannelBlocks:
    """Where the inner contexts' channel blocks lie on the mixer (see the module docstring).

    A plain class, not a frozen model: it is changed in place. The blocks lie in ``base .. top-1``,
    reserved; ``held`` maps each held block's first channel to its size, and the gaps between
    them are free. The layout belongs to the mixer whose channel count it last saw: a restarted
    mixer (back at its default count) is laid out afresh, and ``generation`` then moves so a
    block from before is never freed into the new layout.

    Attributes:
        channel_count: The mixer's channel count when the layout last changed it or saw it.
        base: The first channel blocks may use (the default partition's reservation then).
        top: One past the highest channel ever given to a block (the reservation covers it).
        held: Each held block's first channel and its size.
        generation: Moves each time the layout is forgotten.

    """

    def __init__(self) -> None:
        """Start with nothing laid out."""
        self.channel_count = 0
        self.base = 0
        self.top = 0
        self.held: dict[int, int] = {}
        self.generation = 0

    def forget(self) -> None:
        """Forget the layout: nothing laid out, and blocks from before are never freed."""
        self.channel_count = 0
        self.base = 0
        self.top = 0
        self.held.clear()
        self.generation += 1

    def first_free_start(self, *, size: int) -> int:
        """The first channel of the lowest gap holding ``size`` channels (first fit).

        Args:
            size: The block's channel count.

        Returns:
            The start: a gap between held blocks, else right after the highest held one (the
            layout's top grows when the block reaches past it).
        """
        cursor = self.base
        for start, length in sorted(self.held.items()):
            if start - cursor >= size:
                return cursor
            cursor = start + length
        return cursor


class _EveryChannelReservation:
    """Whether ``every_channel_reserved`` is in force, and how deeply nested.

    A plain class, not a frozen model: it is changed in place.

    Attributes:
        depth: The nesting depth; 0 when not in force.

    """

    def __init__(self) -> None:
        """Start not in force."""
        self.depth = 0


_channel_blocks = _ChannelBlocks()
_every_channel_reservation = _EveryChannelReservation()


@dataclasses.dataclass(frozen=True, slots=True)
class ChannelPartition:
    """Which mixer channels belong to whom (impl spec 7.1).

    Attributes:
        live: The live voices' channel indices.
        library: The voice table's channel indices.
        legacy_count: The unreserved channels left for ``Sound.play()`` callers.
    """

    live: tuple[int, ...]
    library: tuple[int, ...]
    legacy_count: int


class ChannelsHeldError(RuntimeError):
    """A default partition would cover channels an inner context's block holds."""


def _check_channel_counts(**counts: int) -> None:
    """Refuse a negative channel count, naming it.

    Args:
        **counts: Each count by its argument's name.

    Raises:
        ValueError: If a count is negative.
    """
    for name, count in counts.items():
        if count < 0:
            message = f'{name} must be >= 0, got {count}'
            raise ValueError(message)


def _laid_out_blocks() -> _ChannelBlocks | None:
    """The blocks' layout, when one is laid out on the running mixer.

    Returns:
        The layout, or None without a mixer, before any block, or after a restart.
    """
    blocks = _channel_blocks
    if pygame.mixer.get_init() is None or blocks.top == blocks.base:
        return None
    if blocks.channel_count != pygame.mixer.get_num_channels():
        return None
    return blocks


def _logical_reserved_count() -> int:
    """The channels that are reserved outside ``every_channel_reserved``.

    Returns:
        The default partition's reserved channels, or the blocks' top when it is higher.
    """
    blocks = _laid_out_blocks()
    return max(reserved_channel_count(), 0 if blocks is None else blocks.top)


def _apply_the_reservation() -> None:
    """Reserve what should be: every channel while ``every_channel_reserved`` is in force."""
    if _every_channel_reservation.depth > 0:
        pygame.mixer.set_reserved(pygame.mixer.get_num_channels())
    else:
        pygame.mixer.set_reserved(_logical_reserved_count())


def _remember_the_channel_count() -> None:
    """Record the mixer's channel count, grown by a partition or a block, in both records."""
    channel_count = pygame.mixer.get_num_channels()
    if _partitioned_mixer:
        _partitioned_mixer['channel_count'] = channel_count
    _channel_blocks.channel_count = channel_count


def reserve_channels(
    *, live_pool: int, library_channels: int, legacy_channels: int
) -> ChannelPartition:
    """Partition the mixer's channels; call once at startup before any sound plays.

    Sets the channel count to ``live_pool + library_channels + legacy_channels`` and reserves
    channels ``0 .. live_pool + library_channels - 1``, so ``Sound.play()`` reaches only the
    legacy channels. Nothing is playing yet, so the channels changed are idle. Blocks laid out
    above an earlier partition stay reserved, with the legacy channels above them (the module
    docstring); while ``every_channel_reserved`` is in force every channel stays reserved.

    Args:
        live_pool: Channels for live voices (``--live-voice-pool``).
        library_channels: Channels for the voice table (``--sound-channels``).
        legacy_channels: Unreserved channels for ``Sound.play()`` (pygame's default is 8).

    Returns:
        The partition (empty without a mixer).

    Raises:
        ChannelsHeldError: If the partition's channels would cover a held block.
    """
    _check_channel_counts(
        live_pool=live_pool, library_channels=library_channels, legacy_channels=legacy_channels
    )
    if pygame.mixer.get_init() is None:
        return ChannelPartition(live=(), library=(), legacy_count=0)
    requested_count = live_pool + library_channels
    blocks = _laid_out_blocks()
    if blocks is not None and requested_count > blocks.base:
        if blocks.held:
            message = (
                f'the partition asks for channels 0-{requested_count - 1}, but inner contexts '
                f'hold channel blocks from channel {blocks.base}'
            )
            raise ChannelsHeldError(message)
        # Nothing held: the blocks are laid out afresh, above this partition
        _channel_blocks.forget()
        blocks = None
    total_channels = max(requested_count, 0 if blocks is None else blocks.top) + legacy_channels
    # The channel table only grows. A second engine in one process (a test run, a launcher)
    # finds the count it set already there: changing it again would be needless, and every
    # set_num_channels reallocates pygame's channel table while the audio thread may still finish
    # a sound on it (BUGS.md #145). A smaller count would also stop sounds on the removed
    # channels (pygame-ce 2.5.8). A restarted mixer is back at its default count, so it grows
    # again.
    if pygame.mixer.get_num_channels() < total_channels:
        pygame.mixer.set_num_channels(total_channels)
    channel_count = pygame.mixer.get_num_channels()
    reserved_count = min(requested_count, channel_count)
    _partitioned_mixer.clear()
    _partitioned_mixer.update(channel_count=channel_count, reserved_count=reserved_count)
    if blocks is not None:
        blocks.channel_count = channel_count
    _apply_the_reservation()
    return ChannelPartition(
        live=tuple(range(min(live_pool, reserved_count))),
        library=tuple(range(live_pool, reserved_count)),
        legacy_count=channel_count - _logical_reserved_count(),
    )


def release_channels() -> None:
    """Give back the partition's reservation (shutdown), so a restarted mixer can play anywhere.

    SDL_mixer keeps its reservation across ``pygame.mixer.quit()`` and a new ``init()``, while the
    restarted mixer is back at 8 channels (pygame-ce 2.5.8): a ``Sound.play()`` on it would then
    land on a channel pygame does not know and raise ``IndexError: invalid channel index``. The
    inner contexts' blocks are forgotten with it. Nothing happens without a mixer.
    """
    _partitioned_mixer.clear()
    _channel_blocks.forget()
    if pygame.mixer.get_init() is not None:
        pygame.mixer.set_reserved(0)


def reserved_channel_count() -> int:
    """The channels the last partition reserved on the running mixer.

    pygame cannot report its reservation, so the last partition's is remembered with the
    channel count it left; a restarted mixer is back at its default count and no longer matches.
    The blocks above it are not counted (they are the inner contexts').

    Returns:
        The reserved channel count, or 0 without a mixer, a partition, or after a restart.
    """
    if pygame.mixer.get_init() is None or not _partitioned_mixer:
        return 0
    if pygame.mixer.get_num_channels() != _partitioned_mixer['channel_count']:
        return 0
    return _partitioned_mixer['reserved_count']


def legacy_channel_indices(*, partition: ChannelPartition) -> range:
    """The channels left to ``Sound.play()`` callers, as a partition's table shows them.

    They follow the partition's own channels, or the blocks above them (the module docstring).

    Args:
        partition: The partition (its own channels and its legacy count).

    Returns:
        ``legacy_count`` channels from the first one above the partition and every block.
    """
    first_legacy = max(
        max((*partition.live, *partition.library), default=-1) + 1, _logical_reserved_count()
    )
    return range(first_legacy, first_legacy + partition.legacy_count)


@dataclasses.dataclass(slots=True)
class _ChannelBlockHolder:
    """A context's channel block, or None until it takes one (changed in place).

    Attributes:
        partition: The block's channels.
        generation: The layout's generation it was taken in.
    """

    partition: ChannelPartition | None = None
    generation: int = 0


# Each engine context's channel block (glitchygames.engine_context; Arcade sub-plan 4, decision 4):
# only an inner context takes one, its engine's partition (GameEngine.reserved_channel_partition)
CHANNEL_BLOCK_SLOT: ContextSlot[_ChannelBlockHolder] = ContextSlot(
    name='glitchygames.audio.voices.channel_block', factory=_ChannelBlockHolder
)


def context_channel_block(*, live_pool: int, library_channels: int) -> ChannelPartition:
    """The current context's channel block, taken on its first call (an inner context's partition).

    The block is ``library_channels`` channels for its voice table, then ``live_pool`` for its
    live voices, in the lowest free gap above the default partition (first fit), else on top: the
    mixer grows by the block and the reservation is raised over it, the legacy channels moving
    above it, as many as before (the module docstring). A later call returns the same block,
    whatever it asks for; one on a restarted mixer takes a new one. Without a mixer the empty
    partition is returned and nothing is kept, so a later call (once the mixer runs) takes one.

    Args:
        live_pool: The live voices' channels (the context's ``--live-voice-pool``).
        library_channels: The voice table's channels (the context's ``--sound-channels``).

    Returns:
        The block, as a partition.
    """
    _check_channel_counts(live_pool=live_pool, library_channels=library_channels)
    if pygame.mixer.get_init() is None:
        return ChannelPartition(live=(), library=(), legacy_count=0)
    holder = current_context().value(slot=CHANNEL_BLOCK_SLOT)
    blocks = _channel_blocks
    if (
        holder.partition is not None
        and holder.generation == blocks.generation
        and _laid_out_blocks() is not None
    ):
        return holder.partition
    if _laid_out_blocks() is None:
        # Nothing laid out on this mixer (none yet, or on a mixer since restarted, whose blocks
        # are gone with it): blocks start right above the default partition
        blocks.forget()
        blocks.base = blocks.top = reserved_channel_count()
        blocks.channel_count = pygame.mixer.get_num_channels()
    size = live_pool + library_channels
    legacy_count = pygame.mixer.get_num_channels() - _logical_reserved_count()
    if size == 0:
        return ChannelPartition(live=(), library=(), legacy_count=legacy_count)
    start = blocks.first_free_start(size=size)
    end = start + size
    if end > blocks.top:
        # As many legacy channels as before, above the new top. The new top is above every
        # reserved channel, so this always grows the mixer, never shrinks it (BUGS.md #145)
        pygame.mixer.set_num_channels(end + legacy_count)
        blocks.top = end
        _remember_the_channel_count()
        _apply_the_reservation()
    blocks.held[start] = size
    partition = ChannelPartition(
        live=tuple(range(start + library_channels, end)),
        library=tuple(range(start, start + library_channels)),
        legacy_count=pygame.mixer.get_num_channels() - _logical_reserved_count(),
    )
    holder.partition = partition
    holder.generation = blocks.generation
    return partition


def free_context_channel_block() -> None:
    """Give the current context's channel block back (``InnerGame.finish``), for the next one.

    Its channels stay reserved (nothing lowers the reservation) and free for the next block. A
    block from before a restart or ``release_channels`` frees nothing. Nothing happens for a
    context without one.
    """
    holder = current_context().value(slot=CHANNEL_BLOCK_SLOT)
    partition = holder.partition
    holder.partition = None
    if partition is None or holder.generation != _channel_blocks.generation:
        return
    _channel_blocks.held.pop(min((*partition.library, *partition.live)), None)


@contextlib.contextmanager
def every_channel_reserved() -> Generator[None]:
    """Reserve every mixer channel for the body, then put the reservation back as it was.

    With every channel reserved, SDL finds no channel for a plain ``Sound.play()``, which then
    returns None and starts nothing, as on a busy mixer; an explicit ``Channel(index).play()``
    still plays. A silent inner game's build, steps and finish run inside it (Arcade sub-plan 4,
    decision 2), so its plain plays reach no channel and take none from the heard game.

    pygame cannot report its reservation, so the one put back is the last partition's
    (``reserved_channel_count``, read before) with the blocks laid out above it, on the mixer's
    channel count afterwards: a partition made inside (an inner build re-partitioning) neither
    keeps its reservation nor is remembered, and a mixer grown inside keeps the reservation from
    before. A block taken inside (a silent inner build's) keeps every channel reserved until the
    body ends, then stays reserved. A nested call (one silent game's call inside another's) only
    runs its body: the outermost puts the reservation back. The channel count is read when
    reserving. Without a mixer before or after the body, nothing is reserved or put back. The
    body's exceptions propagate, the reservation put back first.

    Yields:
        Nothing; the body runs with every channel reserved.
    """
    if pygame.mixer.get_init() is None:
        yield
        return
    reservation = _every_channel_reservation
    if reservation.depth > 0:
        reservation.depth += 1
        try:
            yield
        finally:
            reservation.depth -= 1
        return
    reserved_before = reserved_channel_count()
    reservation.depth = 1
    pygame.mixer.set_reserved(pygame.mixer.get_num_channels())
    try:
        yield
    finally:
        reservation.depth = 0
        if pygame.mixer.get_init() is not None:
            channel_count = pygame.mixer.get_num_channels()
            _partitioned_mixer.clear()
            if reserved_before > 0:
                _partitioned_mixer.update(
                    channel_count=channel_count,
                    reserved_count=min(reserved_before, channel_count),
                )
            _apply_the_reservation()


def constant_power_gains(*, pan: float, gain: float) -> tuple[float, float]:
    """Left and right channel gains for a pan, by the constant-power law (impl spec 7.2).

    left = gain·cos(θ), right = gain·sin(θ), θ = (pan + 1)·π/4: -3 dB on each side at the centre.

    Args:
        pan: -1 (left) to 1 (right).
        gain: The overall gain.

    Returns:
        The (left, right) gains.
    """
    angle = (pan + 1.0) * math.pi / 4.0
    return gain * math.cos(angle), gain * math.sin(angle)


def _check_range(name: str, value: float, *, low: float, high: float) -> None:
    """Refuse a value outside ``low .. high`` (NaN included).

    Raises:
        ValueError: Naming the parameter and its range.
    """
    if not low <= value <= high:
        message = f'{name} must be between {low} and {high}, got {value}'
        raise ValueError(message)


def _check_fade(fade: float) -> None:
    """Refuse a negative (or NaN) fade.

    Raises:
        ValueError: Naming the fade.
    """
    if not fade >= 0.0:
        message = f'fade must be >= 0 seconds, got {fade}'
        raise ValueError(message)


@dataclasses.dataclass(frozen=True, slots=True)
class ChannelState:
    """One mixer channel as the debug panel shows it.

    Attributes:
        index: The channel index.
        group: ``live``, ``library`` or ``legacy``.
        state: ``idle``, ``playing``, ``fading`` or ``paused``.
    """

    index: int
    group: str
    state: str


@dataclasses.dataclass(frozen=True, slots=True)
class VoiceCounters:
    """What the table had to do under load (feature spec 6.2).

    Attributes:
        steals: Voices stolen for a new play.
        delayed_plays: Plays that waited one frame for their stolen channel.
        dropped_plays: Plays with no channel and nothing to steal, and plays of a sound with no
            samples (never given to the device).
    """

    steals: int
    delayed_plays: int
    dropped_plays: int


@dataclasses.dataclass(frozen=True, slots=True)
class SoundHandle:
    """A play: its slot and that slot's generation when the play started (impl spec 4.4).

    Every method returns ``False`` once the voice has ended (or for a play that never started),
    and never touches a later voice in the same slot. The handle holds no sound.

    Attributes:
        slot: The voice table slot.
        generation: The slot's generation for this play.
        table: The table the handle belongs to (not part of its value).
    """

    slot: int
    generation: int
    table: VoiceTable | None = dataclasses.field(default=None, compare=False, repr=False)

    def stop(self, *, fade: float = DEFAULT_STOP_FADE_SECONDS) -> bool:
        """Fade the voice out over ``fade`` seconds (at least 5 ms).

        Returns:
            Whether the voice was playing.
        """
        return self.table is not None and self.table.stop_voice(self, fade=fade)

    def cancel(self) -> bool:
        """End the voice with a 5 ms de-click fade.

        Returns:
            Whether the voice was playing.
        """
        return self.table is not None and self.table.stop_voice(self, fade=CANCEL_FADE_SECONDS)

    def release(self) -> bool:
        """End a looping voice after its current pass.

        Returns:
            Whether the voice is now releasing; False for a non-looping voice, whose release is
            part of its audio, and for an ended one.
        """
        return self.table is not None and self.table.release_voice(self)

    @property
    def is_playing(self) -> bool:
        """Whether the voice is playing (paused and waiting voices count), by its played time."""
        return self.table is not None and self.table.voice_is_playing(self)

    def set_volume(self, volume: float, *, fade: float = 0.0) -> bool:
        """Change the voice's volume, at once or stepped per frame over ``fade`` seconds.

        Returns:
            Whether the voice was playing.
        """
        return self.table is not None and self.table.set_voice_volume(self, volume, fade=fade)

    def set_pan(self, pan: float) -> bool:
        """Change the voice's pan, -1 (left) to 1 (right).

        Returns:
            Whether the voice was playing.
        """
        return self.table is not None and self.table.set_voice_pan(self, pan)


# A steal counts as recent for this many frames (the debug panel flashes the channel)
RECENT_STEAL_FRAMES = 10


def _is_among(owners: Collection[object], owner: object) -> bool:
    """Whether ``owner`` is one of ``owners``, by identity (owners are compared as objects).

    Returns:
        True when it is.
    """
    return any(candidate is owner for candidate in owners)


class _SlotState(enum.Enum):
    """What a library channel is doing, as the table sees it."""

    IDLE = 'idle'
    PLAYING = 'playing'
    PAUSED = 'paused'
    FADING = 'fading'  # no voice; a stop, steal or cancel fade is running out
    WAITING = 'waiting'  # fading from a steal; the stealer starts on the next advance


# The debug panel's names for each state (a waiting channel is still fading)
_SNAPSHOT_STATE = {
    _SlotState.IDLE: 'idle',
    _SlotState.PLAYING: 'playing',
    _SlotState.PAUSED: 'paused',
    _SlotState.FADING: 'fading',
    _SlotState.WAITING: 'fading',
}


@dataclasses.dataclass(slots=True)
class _VolumeFade:
    """A volume change stepped once per frame."""

    start: float
    target: float
    seconds: float
    elapsed: float = 0.0


@dataclasses.dataclass(slots=True)
class _Voice:
    """One play of a sound."""

    sound: Sound
    mixer_sound: pygame.mixer.Sound
    owner: object
    bus: str
    volume: float
    pan: float
    priority: int
    loop: bool
    persist: bool
    play_number: int
    played_seconds: float = 0.0
    release_ends_at: float | None = None
    release_fade_pending: bool = False
    volume_fade: _VolumeFade | None = None

    @property
    def releasing(self) -> bool:
        """Whether ``release()`` was called."""
        return self.release_ends_at is not None

    def has_ended(self) -> bool:
        """Whether the voice's played time has reached its end.

        Returns:
            True when a released loop reached its pass's end, or a one-shot its length.
        """
        if self.release_ends_at is not None:
            return self.played_seconds >= self.release_ends_at - TIME_TOLERANCE_SECONDS
        if self.loop:
            return False
        return self.played_seconds >= self.sound.length - TIME_TOLERANCE_SECONDS


@dataclasses.dataclass(slots=True, eq=False)
class _Slot:
    """One library channel and its current voice.

    ``held_sounds`` keeps the last sound the channel played alive until the channel is reused
    or stopped: a pygame sound freed while a channel plays it is halted by SDL_mixer, which
    would cut a fade (or the last device buffer of a voice the table already ended).
    """

    number: int
    channel_index: int
    generation: int = 0
    state: _SlotState = _SlotState.IDLE
    voice: _Voice | None = None
    fade_seconds_left: float = 0.0
    held_sounds: tuple[Sound, pygame.mixer.Sound] | None = None
    # True once the silencer stopped the channel under a voice or a fade, until the next play
    # on it: the table's state goes on by frame time, but the channel is quiet
    device_stopped: bool = False
    # True while the slot's voice (or its fade) is on the mixer: it started while the table's
    # context was audible, and the context has not gone silent since (fade_out_of_the_mixer)
    heard: bool = False


class VoiceTable:
    """The library's voices on its reserved channels."""

    def __init__(
        self,
        *,
        partition: ChannelPartition,
        buses: BusTree,
        compile_for_play: Callable[[Sound], Sound],
    ) -> None:
        """Make a table over the partition's library channels, for the current engine context.

        The context the table is made in is the one whose audio route decides whether it reaches
        the mixer (see the module docstring).

        Args:
            partition: The channel partition (``reserve_channels``).
            buses: The bus tree whose gains and reservations apply.
            compile_for_play: The library's ``compile_for_play``, called on every play.
        """
        self._audio_route = current_context().value(slot=AUDIO_ROUTE_SLOT)
        self._partition = partition
        self._buses = buses
        self._compile_for_play = compile_for_play
        self._slots = [
            _Slot(number=number, channel_index=index)
            for number, index in enumerate(partition.library)
        ]
        self._play_numbers = itertools.count()
        self._applied_bus_revision = buses.revision
        self._steals = 0
        # Frames (advances) run so far, and the frame of each channel's latest steal; one entry
        # per library channel at most, so it stays bounded (the debug panel's steal flash)
        self._frames_advanced = 0
        self._steal_frames: dict[int, int] = {}
        self._delayed_plays = 0
        self._dropped_plays = 0
        self._warned_no_mixer = False
        self._closed = False

    # --- Plays ---

    def play(  # ruff: ignore[too-many-arguments] - impl spec 8's playback arguments
        self,
        sound: Sound,
        *,
        volume: float,
        pan: float,
        bus: str,
        priority: int,
        loop: bool,
        persist: bool,
        owner: object,
    ) -> SoundHandle:
        """Play a sound on a library channel.

        Args:
            sound: The sound (``compile_for_play`` gives the one to play).
            volume: 0-1.
            pan: -1 (left) to 1 (right).
            bus: The bus name; an unknown one raises KeyError naming the buses.
            priority: 0-100; stealing takes only voices of lower or equal priority.
            loop: Whether the sound loops until stopped or released.
            persist: Whether the voice outlives its owner's clean-up (``stop_owner``).
            owner: Who started it (a scene, the engine's system owner); opaque.

        Returns:
            The handle; a handle answering ``False`` when there is no mixer, the table is closed,
            the sound has no samples, or the play was dropped.

        """
        _check_range('volume', volume, low=0.0, high=1.0)
        _check_range('pan', pan, low=-1.0, high=1.0)
        _check_range('priority', priority, low=MINIMUM_PRIORITY, high=MAXIMUM_PRIORITY)
        self._buses[bus]  # raises KeyError naming the buses for an unknown bus
        silent = SoundHandle(slot=-1, generation=-1, table=self)
        if self._closed:
            return silent
        if pygame.mixer.get_init() is None:
            if not self._warned_no_mixer:
                self._warned_no_mixer = True
                log.warning('no mixer: sound library plays are silent')
            return silent
        compiled = self._compile_for_play(sound)
        mixer_sound = self._playable_mixer_sound(compiled)
        if mixer_sound is None:
            return silent
        voice = _Voice(
            sound=compiled,
            mixer_sound=mixer_sound,
            owner=owner,
            bus=bus,
            volume=float(volume),
            pan=float(pan),
            priority=priority,
            loop=loop,
            persist=persist,
            play_number=next(self._play_numbers),
        )
        slot = self._free_slot_for(bus)
        if slot is None:
            victim = self._victim_for(bus, priority=priority)
            if victim is None:
                self._dropped_plays += 1
                return silent
            self._steal(victim)
            # Stealing may have brought the bus under its reservation, opening a free channel
            slot = self._free_slot_for(bus)
            if slot is None:
                victim.state = _SlotState.WAITING
                victim.voice = voice
                self._delayed_plays += 1
                return SoundHandle(slot=victim.number, generation=victim.generation, table=self)
        self._start(slot, voice)
        return SoundHandle(slot=slot.number, generation=slot.generation, table=self)

    def _playable_mixer_sound(self, compiled: Sound) -> pygame.mixer.Sound | None:
        """The sound's pygame sound, or None when there is nothing to hand the device.

        SDL_mixer's mixing thread can loop forever on, or crash with, a zero-length chunk whether
        or not it loops, so an empty sound never reaches a channel. It is counted with the
        dropped plays: the game asked for a sound and got none.

        Returns:
            The pygame sound, or None without a mixer, before compiling, or with no samples.
        """
        mixer_sound = compiled.mixer_sound()
        if mixer_sound is not None and mixer_sound.get_length() <= 0.0:
            self._dropped_plays += 1
            return None
        return mixer_sound

    def is_playing_sound(self, sound: Sound) -> bool:
        """Whether any channel still uses the sound (playing, paused, waiting or fading).

        The library asks this before evicting a sound: a fading channel still reads its samples.

        Returns:
            True while a voice or a fade uses a sound of the same identity.
        """
        for slot in self._slots:
            in_use = slot.voice.sound if slot.voice is not None else None
            if in_use is None and slot.state is _SlotState.FADING and slot.held_sounds:
                in_use = slot.held_sounds[0]
            if in_use is not None and in_use.identity_key == sound.identity_key:
                return True
        return False

    @property
    def reaches_the_mixer(self) -> bool:
        """Whether the table's context is audible, so its heard slots' channels are touched."""
        return self._audio_route.audible

    @property
    def voice_count(self) -> int:
        """The voices playing, paused or waiting for their channel (by played time)."""
        return sum(1 for slot in self._slots if slot.voice is not None)

    @property
    def counters(self) -> VoiceCounters:
        """Steals, delayed plays and dropped plays so far."""
        return VoiceCounters(
            steals=self._steals,
            delayed_plays=self._delayed_plays,
            dropped_plays=self._dropped_plays,
        )

    # --- Frames ---

    def advance(self, *, dt: float, paused_owners: Collection[object]) -> None:
        """Move every voice by one served frame (impl spec 7.3).

        Playing voices gain ``dt`` of played time and end at their length (or a released loop
        at its pass's end); a voice whose owner is in ``paused_owners`` is paused on its channel
        and gains no time until its owner is not; fades run out; plays waiting for a stolen
        channel start; bus changes and per-frame volume fades reach the channels.

        Args:
            dt: The frame's served time in seconds (a replay's recorded dt).
            paused_owners: Owners whose voices are held (a pause screen, a playback scope).
        """
        self._frames_advanced += 1
        buses_changed = self._buses.revision != self._applied_bus_revision
        self._applied_bus_revision = self._buses.revision
        for slot in self._slots:
            voice = slot.voice
            if slot.state is _SlotState.FADING:
                slot.fade_seconds_left -= dt
                if slot.fade_seconds_left <= TIME_TOLERANCE_SECONDS:
                    slot.state = _SlotState.IDLE
            elif voice is None:
                continue
            elif slot.state is _SlotState.PLAYING:
                self._advance_playing(
                    slot,
                    voice,
                    dt=dt,
                    paused=_is_among(paused_owners, voice.owner),
                    buses_changed=buses_changed,
                )
            elif slot.state is _SlotState.PAUSED:
                if not _is_among(paused_owners, voice.owner):
                    self._resume(slot, voice)
                if buses_changed:
                    self._apply_gains(slot, voice)
            else:  # WAITING: its stolen channel has had a frame to fade
                self._start(slot, voice)
                if _is_among(paused_owners, voice.owner):
                    self._pause(slot)

    def _advance_playing(
        self, slot: _Slot, voice: _Voice, *, dt: float, paused: bool, buses_changed: bool
    ) -> None:
        """Add a frame to a playing voice; end it, re-apply its gains or pause it."""
        voice.played_seconds += dt
        if voice.has_ended():
            self._end_voice(slot)
            return
        if self._step_volume_fade(voice, dt) or buses_changed:
            self._apply_gains(slot, voice)
        if paused:
            self._pause(slot)

    def _pause(self, slot: _Slot) -> None:
        """Hold the slot's voice: its channel pauses (when heard) and its time stops."""
        if self._sounds(slot):
            pygame.mixer.Channel(slot.channel_index).pause()
        slot.state = _SlotState.PAUSED

    def _resume(self, slot: _Slot, voice: _Voice) -> None:
        """Let a held voice play on: its channel unpauses (when heard) and a release fades."""
        if self._sounds(slot):
            pygame.mixer.Channel(slot.channel_index).unpause()
        slot.state = _SlotState.PLAYING
        self._fade_out_release(slot, voice)

    def silenced(self, channel_index: int) -> None:
        """A channel was stopped outside the table (``FrameSilencer``): only the channel is quiet.

        The slot's voice (or fade) stays in the table with its generation and played time, so
        what the game sees is what it saw in the run that was not silenced (impl spec 7.3); the
        slot is marked device-stopped until its channel's next play.

        Args:
            channel_index: The mixer channel; channels outside the library are ignored.
        """
        for slot in self._slots:
            if slot.channel_index == channel_index and slot.state is not _SlotState.IDLE:
                slot.device_stopped = True

    def fade_out_of_the_mixer(self, *, fade_seconds: float) -> None:
        """Fade every heard channel out, then leave the mixer: the context is going silent.

        Called while the context is still audible, just before its route turns silent (the
        module docstring has the order and the rules). Only the channels change: every voice
        stays in the table with its played time and generation, so what the game sees goes on as
        it would heard. Every slot is unheard afterwards, so nothing under way is heard again.

        Args:
            fade_seconds: The fade (the scene clean-up's 50 ms).
        """
        _check_fade(fade_seconds)
        for slot in self._slots:
            # A channel the silencer stopped no longer sounds the context's voice: left alone
            was_sounding = self._sounds(slot) and not slot.device_stopped
            slot.heard = False
            if not was_sounding:
                continue
            device_fade_seconds_left = _device_fade_seconds_left(slot)
            channel = pygame.mixer.Channel(slot.channel_index)
            if slot.state is _SlotState.PAUSED or (
                device_fade_seconds_left is not None
                and device_fade_seconds_left > fade_seconds + TIME_TOLERANCE_SECONDS
            ):
                channel.stop()
            elif device_fade_seconds_left is None and slot.state is _SlotState.PLAYING:
                channel.fadeout(round(fade_seconds * MILLISECONDS_PER_SECOND))

    def end_voices_without_the_device(self) -> None:
        """End every voice in the table at once, touching no channel (the mixer's are gone).

        For a close on a mixer stopped or restarted with fewer channels: there is no channel to
        fade, so the voices end and their handles answer ``False``.
        """
        for slot in self._slots:
            if slot.voice is not None:
                slot.generation += 1
            slot.voice = None
            slot.state = _SlotState.IDLE
            slot.held_sounds = None

    def stop_owner(self, owner: object, *, fade_seconds: float = DEFAULT_STOP_FADE_SECONDS) -> None:
        """Fade out an owner's voices (scene clean-up), except those played with ``persist``.

        Args:
            owner: The owner.
            fade_seconds: The fade.
        """
        for slot in self._slots:
            if slot.voice is not None and slot.voice.owner is owner and not slot.voice.persist:
                self._stop_slot(slot, fade_seconds=fade_seconds)

    def stop_buses(self, bus_names: Collection[str] | None, *, fade_seconds: float) -> None:
        """Fade out the voices on some buses (every voice for None), persisted ones included.

        Args:
            bus_names: The buses whose voices stop, or None for every voice.
            fade_seconds: The fade (at least 5 ms).
        """
        _check_fade(fade_seconds)
        for slot in self._slots:
            if slot.voice is not None and (bus_names is None or slot.voice.bus in bus_names):
                self._stop_slot(slot, fade_seconds=fade_seconds)

    def close(self, *, fade_seconds: float = DEFAULT_STOP_FADE_SECONDS) -> None:
        """Fade out every voice (shutdown); later plays are silent.

        Args:
            fade_seconds: The fade.
        """
        self._closed = True
        for slot in self._slots:
            if slot.voice is not None:
                self._stop_slot(slot, fade_seconds=fade_seconds)

    def recently_stolen_channels(self) -> frozenset[int]:
        """The channels whose voice was stolen within the last ``RECENT_STEAL_FRAMES`` frames.

        Returns:
            The channel indexes (for the debug panel's flash).
        """
        return frozenset(
            index
            for index, frame in self._steal_frames.items()
            if self._frames_advanced - frame < RECENT_STEAL_FRAMES
        )

    def snapshot(self) -> tuple[ChannelState, ...]:
        """Every channel's group and state, for the debug panel.

        Live and legacy channels belong to others, so their state is the device's busy flag (in a
        silent context, ``idle``: it reads no channel). A library channel the silencer stopped
        shows ``idle`` until its next play, whatever its voice is doing in the table.

        Returns:
            One state per channel, by index.
        """
        reads_the_device = self.reaches_the_mixer
        states = [
            ChannelState(
                index=index,
                group='live',
                state=_device_state(index, reads_the_device=reads_the_device),
            )
            for index in self._partition.live
        ]
        states.extend(
            ChannelState(
                index=slot.channel_index,
                group='library',
                state='idle' if slot.device_stopped else _SNAPSHOT_STATE[slot.state],
            )
            for slot in self._slots
        )
        # Above the partition and every inner context's block (an inner context's own block
        # holds its library below its live pool)
        states.extend(
            ChannelState(
                index=index,
                group='legacy',
                state=_device_state(index, reads_the_device=reads_the_device),
            )
            for index in legacy_channel_indices(partition=self._partition)
        )
        return tuple(sorted(states, key=operator.attrgetter('index')))

    # --- Handle calls (SoundHandle's methods) ---

    def voice_is_playing(self, handle: SoundHandle) -> bool:
        """Whether the handle's voice is still playing (paused and waiting count).

        Returns:
            The answer.
        """
        return self._slot_for(handle) is not None

    def stop_voice(self, handle: SoundHandle, *, fade: float) -> bool:
        """Fade the handle's voice out over ``fade`` seconds (at least 5 ms).

        Returns:
            Whether the voice was playing.
        """
        _check_fade(fade)
        slot = self._slot_for(handle)
        if slot is None:
            return False
        self._stop_slot(slot, fade_seconds=fade)
        return True

    def release_voice(self, handle: SoundHandle) -> bool:
        """End the handle's looping voice after its current pass.

        Returns:
            Whether the voice is releasing (False for a non-looping or ended voice).
        """
        slot = self._slot_for(handle)
        if slot is None or slot.voice is None or not slot.voice.loop:
            return False
        voice = slot.voice
        if voice.releasing:
            return True
        length = voice.sound.length
        voice.release_ends_at = voice.played_seconds + length - voice.played_seconds % length
        voice.release_fade_pending = True
        if slot.state is _SlotState.PLAYING:
            self._fade_out_release(slot, voice)
        return True

    def set_voice_volume(self, handle: SoundHandle, volume: float, *, fade: float) -> bool:
        """Set the handle's voice volume, at once or stepped per frame over ``fade``.

        Returns:
            Whether the voice was playing.
        """
        _check_range('volume', volume, low=0.0, high=1.0)
        _check_fade(fade)
        slot = self._slot_for(handle)
        if slot is None or slot.voice is None:
            return False
        voice = slot.voice
        if fade > 0.0:
            voice.volume_fade = _VolumeFade(start=voice.volume, target=float(volume), seconds=fade)
            return True
        voice.volume_fade = None
        voice.volume = float(volume)
        self._apply_gains(slot, voice)
        return True

    def set_voice_pan(self, handle: SoundHandle, pan: float) -> bool:
        """Set the handle's voice pan.

        Returns:
            Whether the voice was playing.
        """
        _check_range('pan', pan, low=-1.0, high=1.0)
        slot = self._slot_for(handle)
        if slot is None or slot.voice is None:
            return False
        slot.voice.pan = float(pan)
        self._apply_gains(slot, slot.voice)
        return True

    # --- Inside ---

    def _slot_for(self, handle: SoundHandle) -> _Slot | None:
        """The handle's slot while its voice lives.

        Returns:
            The slot, or None for a stale or silent handle.
        """
        if not 0 <= handle.slot < len(self._slots):
            return None
        slot = self._slots[handle.slot]
        if slot.generation != handle.generation or slot.voice is None:
            return None
        return slot

    def _voices_by_bus(self) -> dict[str, int]:
        """How many voices (playing, paused or waiting) each bus has.

        Returns:
            Bus name to voice count.
        """
        counts: dict[str, int] = {}
        for slot in self._slots:
            if slot.voice is not None:
                counts[slot.voice.bus] = counts.get(slot.voice.bus, 0) + 1
        return counts

    def _free_slot_for(self, bus: str) -> _Slot | None:
        """A free channel ``bus`` may use (impl spec 7.1 step 1; ruling R30).

        Free is decided by the table alone, so whether a play steals is the same in a replay:
        a channel is free when it holds no voice and no fade is running out on it in frame
        time (a voice that ended by played time leaves it free at once). A bus under its
        reservation may take any free channel; otherwise only channels beyond the other buses'
        unmet reservations. The device only chooses among the free channels: the lowest one not
        sounding on the device, else the lowest (cutting at most a device buffer of an ended
        voice's tail). A silent context reads no channel: its choice is the lowest free one.

        Returns:
            The slot, or None.
        """
        free = [slot for slot in self._slots if slot.state is _SlotState.IDLE]
        if not free:
            return None
        voices_by_bus = self._voices_by_bus()
        if voices_by_bus.get(bus, 0) >= self._buses[bus].reserved_channels:
            unmet_elsewhere = sum(
                max(0, self._buses[name].reserved_channels - voices_by_bus.get(name, 0))
                for name in self._buses.names()
                if name != bus
            )
            if len(free) <= unmet_elsewhere:
                return None
        if self.reaches_the_mixer:
            for slot in free:
                if not pygame.mixer.Channel(slot.channel_index).get_busy():
                    return slot
        return free[0]

    def _victim_for(self, bus: str, *, priority: int) -> _Slot | None:
        """The voice to steal for a play on ``bus`` at ``priority`` (impl spec 7.1 step 2).

        Playing voices only (never paused or waiting ones) of lower or equal priority, and
        never one whose bus would fall under its own reservation; releasing first, then lowest
        priority, earliest play, lowest channel. Decided from the table alone (AUD-MIX-003).

        Returns:
            The victim's slot, or None.
        """
        voices_by_bus = self._voices_by_bus()
        candidates: list[tuple[tuple[bool, int, int, int], _Slot]] = []
        for slot in self._slots:
            voice = slot.voice
            if slot.state is not _SlotState.PLAYING or voice is None or voice.priority > priority:
                continue
            if (
                voice.bus != bus
                and voices_by_bus.get(voice.bus, 0) <= self._buses[voice.bus].reserved_channels
            ):
                continue
            order = (not voice.releasing, voice.priority, voice.play_number, slot.channel_index)
            candidates.append((order, slot))
        if not candidates:
            return None
        return min(candidates, key=operator.itemgetter(0))[1]

    def _steal(self, slot: _Slot) -> None:
        """Fade a playing voice over 10 ms (when heard) and end it; its channel is fading."""
        if self._sounds(slot):
            pygame.mixer.Channel(slot.channel_index).fadeout(STEAL_FADE_MILLISECONDS)
        self._fade_slot(slot, fade_seconds=STEAL_FADE_MILLISECONDS / MILLISECONDS_PER_SECOND)
        self._steals += 1
        self._steal_frames[slot.channel_index] = self._frames_advanced

    def _start(self, slot: _Slot, voice: _Voice) -> None:
        """Play a voice on its channel, then set its gains (pygame resets volume on play).

        In a silent context the voice starts in the table only, unheard for its whole life.
        """
        slot.heard = self.reaches_the_mixer
        if slot.heard:
            channel = pygame.mixer.Channel(slot.channel_index)
            channel.play(voice.mixer_sound, loops=-1 if voice.loop else 0)
        slot.voice = voice
        slot.state = _SlotState.PLAYING
        slot.fade_seconds_left = 0.0
        slot.held_sounds = (voice.sound, voice.mixer_sound)
        slot.device_stopped = False
        self._apply_gains(slot, voice)
        self._fade_out_release(slot, voice)

    def _stop_slot(self, slot: _Slot, *, fade_seconds: float) -> None:
        """End a slot's voice with a fade: a waiting voice never starts, a paused one stops."""
        if slot.state is _SlotState.WAITING:
            # The steal's fade keeps running out; the waiting voice simply never starts
            slot.voice = None
            slot.state = _SlotState.FADING
            slot.generation += 1
        elif slot.state is _SlotState.PAUSED:
            # A paused channel cannot fade, and it is silent: stop it now
            if self._sounds(slot):
                pygame.mixer.Channel(slot.channel_index).stop()
            self._end_voice(slot)
        else:
            seconds = max(fade_seconds, MINIMUM_FADE_SECONDS)
            if self._sounds(slot):
                pygame.mixer.Channel(slot.channel_index).fadeout(
                    round(seconds * MILLISECONDS_PER_SECOND)
                )
            self._fade_slot(slot, fade_seconds=seconds)

    def _fade_slot(self, slot: _Slot, *, fade_seconds: float) -> None:
        """End the slot's voice; the channel is fading for ``fade_seconds`` of frame time."""
        slot.voice = None
        slot.state = _SlotState.FADING
        slot.fade_seconds_left = fade_seconds
        slot.generation += 1

    def _end_voice(self, slot: _Slot) -> None:
        """End the slot's voice now; the channel is idle (its sounds stay held, see _Slot)."""
        slot.voice = None
        slot.state = _SlotState.IDLE
        slot.generation += 1

    def _fade_out_release(self, slot: _Slot, voice: _Voice) -> None:
        """Start a released loop's fade over what is left of its pass, once it is playing."""
        if not voice.release_fade_pending or voice.release_ends_at is None:
            return
        voice.release_fade_pending = False
        remaining = max(voice.release_ends_at - voice.played_seconds, MINIMUM_FADE_SECONDS)
        if self._sounds(slot):
            pygame.mixer.Channel(slot.channel_index).fadeout(
                round(remaining * MILLISECONDS_PER_SECOND)
            )

    def _apply_gains(self, slot: _Slot, voice: _Voice) -> None:
        """Set the channel's left and right gains from the voice and its bus (impl spec 7.2)."""
        if slot.state is _SlotState.WAITING or not self._sounds(slot):
            return  # applied when it starts; an unheard channel is never touched
        gain = voice.volume * self._buses[voice.bus].effective_gain()
        left, right = constant_power_gains(pan=voice.pan, gain=gain)
        pygame.mixer.Channel(slot.channel_index).set_volume(left, right)

    def _sounds(self, slot: _Slot) -> bool:
        """Whether the slot's channel may be touched: its voice was heard and still may be.

        Returns:
            True when the slot is heard and the table's context is audible.
        """
        return slot.heard and self.reaches_the_mixer

    @staticmethod
    def _step_volume_fade(voice: _Voice, dt: float) -> bool:
        """Move a volume fade by one frame.

        Returns:
            Whether the volume changed.
        """
        fade = voice.volume_fade
        if fade is None:
            return False
        fade.elapsed += dt
        if fade.elapsed >= fade.seconds - TIME_TOLERANCE_SECONDS:
            voice.volume = fade.target
            voice.volume_fade = None
        else:
            voice.volume = fade.start + (fade.target - fade.start) * fade.elapsed / fade.seconds
        return True


def _device_state(index: int, *, reads_the_device: bool) -> str:
    """A channel the table does not own, as the device reports it.

    Args:
        index: The channel index.
        reads_the_device: False in a silent context, which reads no channel.

    Returns:
        ``playing`` while the device is busy on it (and is read), else ``idle``.
    """
    return 'playing' if reads_the_device and pygame.mixer.Channel(index).get_busy() else 'idle'


def _device_fade_seconds_left(slot: _Slot) -> float | None:
    """How long the slot's channel still fades out on the device, by the table's frame time.

    Returns:
        The seconds left of a stop's or a steal's fade, or of a released loop's fade over what
        is left of its pass; None when the channel is not fading out.
    """
    if slot.state in {_SlotState.FADING, _SlotState.WAITING}:
        return slot.fade_seconds_left
    voice = slot.voice
    if (
        slot.state is _SlotState.PLAYING
        and voice is not None
        and voice.release_ends_at is not None
        and not voice.release_fade_pending
    ):
        return voice.release_ends_at - voice.played_seconds
    return None
