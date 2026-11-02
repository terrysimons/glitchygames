"""The voice table: library plays on reserved mixer channels (impl spec 4.4 and 7.1-7.3).

The mixer's channels are partitioned once at startup (``reserve_channels``): ``0 .. live-1``
for live voices, the next ``library`` channels for this table, and the rest (pygame's default
8) for legacy ``Sound.play()`` callers, which SDL places only on unreserved channels. The table
never calls ``Sound.play()``, so neither side can cut the other off (AUD-MIX-008).

Each library channel is one slot of the table. A play takes the lowest free channel its bus may
use (bus reservations: ``Bus.reserved_channels``), else steals a playing voice of lower or
equal priority (releasing first, then lowest priority, earliest play, lowest channel; decided
from the table alone, so it is deterministic: AUD-MIX-003), else is dropped and counted. A
stolen channel fades with ``Channel.fadeout(10)``; the stealer takes another free channel, or
waits one frame for the stolen one (counted as a delayed play) because ``Channel.play`` on a
fading channel may cut the fade audibly (impl spec 7.1 **[Open]**, verified in Task 13).

What the game sees (``SoundHandle.is_playing``, voices ending) follows each voice's
``played_seconds``, which ``advance`` moves by the served frame time only while the voice is not
paused, never ``Channel.get_busy()`` (impl spec 7.3), so a replay sees the same answers. The
device is asked only whether a table-free channel is still sounding (a fade), which decides
which channel a play lands on, never what the game sees.

Handles are ``(slot, generation)`` values. A slot's generation moves whenever its voice ends,
so a handle whose voice ended, was stolen or was replaced answers ``False`` and never controls
the voice that took its slot later (impl spec 4.4).

``release()`` on a looping voice ends the loop after the current pass: pygame cannot change a
playing channel's loop count, so the channel fades out over what is left of the pass
(``Channel.fadeout``), ending exactly at the pass's end. That pass's remainder is heard fading,
not at full level (a documented simplification; the brief's ruling).
"""

from __future__ import annotations

import dataclasses
import enum
import itertools
import logging
import math
import operator
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

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


def reserve_channels(
    *, live_pool: int, library_channels: int, legacy_channels: int
) -> ChannelPartition:
    """Partition the mixer's channels; call once at startup before any sound plays.

    Sets the channel count to ``live_pool + library_channels + legacy_channels`` and reserves
    channels ``0 .. live_pool + library_channels - 1``, so ``Sound.play()`` reaches only the
    legacy channels. Nothing is playing yet, so the channels changed are idle.

    Args:
        live_pool: Channels for live voices (``--live-voice-pool``).
        library_channels: Channels for the voice table (``--sound-channels``).
        legacy_channels: Unreserved channels for ``Sound.play()`` (pygame's default is 8).

    Returns:
        The partition (empty without a mixer).

    Raises:
        ValueError: If a count is negative.
    """
    for name, count in (
        ('live_pool', live_pool),
        ('library_channels', library_channels),
        ('legacy_channels', legacy_channels),
    ):
        if count < 0:
            message = f'{name} must be >= 0, got {count}'
            raise ValueError(message)
    if pygame.mixer.get_init() is None:
        return ChannelPartition(live=(), library=(), legacy_count=0)
    total_channels = live_pool + library_channels + legacy_channels
    # A second engine in one process (a test run, a launcher) finds the count it set already
    # there: changing it again would be needless, and every set_num_channels reallocates
    # pygame's channel table while the audio thread may still finish a sound on it (BUGS.md
    # #145). A restarted mixer is back at its default count, so it is set again. A smaller count
    # stops sounds on the removed channels (pygame-ce 2.5.8), so this runs before anything plays.
    if pygame.mixer.get_num_channels() != total_channels:
        pygame.mixer.set_num_channels(total_channels)
    reserved_count = pygame.mixer.set_reserved(live_pool + library_channels)
    return ChannelPartition(
        live=tuple(range(min(live_pool, reserved_count))),
        library=tuple(range(live_pool, reserved_count)),
        legacy_count=pygame.mixer.get_num_channels() - reserved_count,
    )


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
        dropped_plays: Plays with no channel and nothing to steal.
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


class VoiceTable:
    """The library's voices on its reserved channels."""

    def __init__(
        self,
        *,
        partition: ChannelPartition,
        buses: BusTree,
        compile_for_play: Callable[[Sound], Sound],
    ) -> None:
        """Make a table over the partition's library channels.

        Args:
            partition: The channel partition (``reserve_channels``).
            buses: The bus tree whose gains and reservations apply.
            compile_for_play: The library's ``compile_for_play``, called on every play.
        """
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
        mixer_sound = compiled.mixer_sound()
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
                    paused=voice.owner in paused_owners,
                    buses_changed=buses_changed,
                )
            elif slot.state is _SlotState.PAUSED:
                if voice.owner not in paused_owners:
                    pygame.mixer.Channel(slot.channel_index).unpause()
                    slot.state = _SlotState.PLAYING
                    self._fade_out_release(slot, voice)
                if buses_changed:
                    self._apply_gains(slot, voice)
            else:  # WAITING: its stolen channel has had a frame to fade
                self._start(slot, voice)
                if voice.owner in paused_owners:
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

    @staticmethod
    def _pause(slot: _Slot) -> None:
        """Hold the slot's voice: its channel pauses and its time stops."""
        pygame.mixer.Channel(slot.channel_index).pause()
        slot.state = _SlotState.PAUSED

    def silenced(self, channel_index: int) -> None:
        """A channel was stopped outside the table (``FrameSilencer``): end its voice.

        Args:
            channel_index: The mixer channel; channels outside the library are ignored.
        """
        for slot in self._slots:
            if slot.channel_index == channel_index:
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
            if slot.voice is not None and slot.voice.owner == owner and not slot.voice.persist:
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

    def snapshot(self) -> tuple[ChannelState, ...]:
        """Every channel's group and state, for the debug panel.

        Live and legacy channels belong to others, so their state is the device's busy flag.

        Returns:
            One state per channel, by index.
        """
        states = [
            ChannelState(index=index, group='live', state=_device_state(index))
            for index in self._partition.live
        ]
        states.extend(
            ChannelState(
                index=slot.channel_index, group='library', state=_SNAPSHOT_STATE[slot.state]
            )
            for slot in self._slots
        )
        first_legacy = len(self._partition.live) + len(self._partition.library)
        states.extend(
            ChannelState(index=index, group='legacy', state=_device_state(index))
            for index in range(first_legacy, first_legacy + self._partition.legacy_count)
        )
        return tuple(states)

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
        """The lowest free channel ``bus`` may use (impl spec 7.1 step 1).

        Free: no voice in the table, and no longer sounding on the device (a stop's fade the
        device finished early counts as free; one still fading does not). A bus under its
        reservation may take any free channel; otherwise only channels beyond the other buses'
        unmet reservations.

        Returns:
            The slot, or None.
        """
        free = [
            slot
            for slot in self._slots
            if slot.state in {_SlotState.IDLE, _SlotState.FADING}
            and not pygame.mixer.Channel(slot.channel_index).get_busy()
        ]
        if not free:
            return None
        voices_by_bus = self._voices_by_bus()
        if voices_by_bus.get(bus, 0) < self._buses[bus].reserved_channels:
            return free[0]
        unmet_elsewhere = sum(
            max(0, self._buses[name].reserved_channels - voices_by_bus.get(name, 0))
            for name in self._buses.names()
            if name != bus
        )
        return free[0] if len(free) > unmet_elsewhere else None

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
        """Fade a playing voice over 10 ms and end it; its channel is fading."""
        pygame.mixer.Channel(slot.channel_index).fadeout(STEAL_FADE_MILLISECONDS)
        self._fade_slot(slot, fade_seconds=STEAL_FADE_MILLISECONDS / MILLISECONDS_PER_SECOND)
        self._steals += 1

    def _start(self, slot: _Slot, voice: _Voice) -> None:
        """Play a voice on its channel, then set its gains (pygame resets volume on play)."""
        channel = pygame.mixer.Channel(slot.channel_index)
        channel.play(voice.mixer_sound, loops=-1 if voice.loop else 0)
        slot.voice = voice
        slot.state = _SlotState.PLAYING
        slot.fade_seconds_left = 0.0
        slot.held_sounds = (voice.sound, voice.mixer_sound)
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
            pygame.mixer.Channel(slot.channel_index).stop()
            self._end_voice(slot)
        else:
            seconds = max(fade_seconds, MINIMUM_FADE_SECONDS)
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
        pygame.mixer.Channel(slot.channel_index).fadeout(round(remaining * MILLISECONDS_PER_SECOND))

    def _apply_gains(self, slot: _Slot, voice: _Voice) -> None:
        """Set the channel's left and right gains from the voice and its bus (impl spec 7.2)."""
        if slot.state is _SlotState.WAITING:
            return  # applied when it starts
        gain = voice.volume * self._buses[voice.bus].effective_gain()
        left, right = constant_power_gains(pan=voice.pan, gain=gain)
        pygame.mixer.Channel(slot.channel_index).set_volume(left, right)

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


def _device_state(index: int) -> str:
    """A channel the table does not own, as the device reports it.

    Returns:
        ``playing`` while the device is busy on it, else ``idle``.
    """
    return 'playing' if pygame.mixer.Channel(index).get_busy() else 'idle'
