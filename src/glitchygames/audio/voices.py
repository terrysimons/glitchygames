"""The voice table: library plays on reserved mixer channels (impl spec 4.4 and 7.1-7.3).

The mixer's channels are partitioned once at startup (``reserve_channels``): ``0 .. live-1``
for live voices, the next ``library`` channels for this table, and the rest (pygame's default
8) for legacy ``Sound.play()`` callers, which SDL places only on unreserved channels. The table
never calls ``Sound.play()``, so neither side can cut the other off (AUD-MIX-008).

An inner context (an Arcade tile; Arcade sub-plan 4, decisions 4 and 5) never partitions the
mixer. A silent context's table touches no channel (below), so only the heard inner game needs
library channels: the host declares once, at startup and before anything plays, how many inner
games it runs (``Scene.INNER_GAMES``, declared with its engine's own partition at construction,
or ``reserve_inner_game_channels`` after ``GameEngine(...)`` and before ``start()``, which has
that engine partition first; without an engine the mixer must be partitioned already, else the
declaration is refused; a growth while a channel plays is refused, by a declaration and by any
partition, ``MixerBusyError``), and the mixer grows that once to hold, right above
the default partition (which keeps its channels), two heard sets of library channels and a live
pool per inner game, with the legacy channels above them all (as many as before) and the
reservation raised over everything below the legacy channels, so a plain ``Sound.play()`` never
lands on them. The mixer never grows again: ``set_num_channels`` reallocates pygame's channel
table without SDL's audio lock while sound plays (BUGS.md #145). An inner context's partition
(``inner_context_partition``) has its recording's ``--sound-channels`` as logical slots, so its
steals and drops are those of the game run alone; while it is heard it holds one heard set
(``take_heard_set``) and slot ``i`` plays on that set's channel ``i``. The two sets alternate:
the game made silent fades out on its set while the newly heard one starts on the other.
Keeping one inner game heard is the host's job: two may be heard at once, one per heard set (the
next made heard before the last is silenced), and a third is refused. Its live voices take a
live pool at build. An inner game built with none declared, or past the declared count, fails
alone (``InnerGameChannelsError``, naming the contexts holding the pools), and
``release_inner_context_channels`` gives everything back at its finish, which the host must call
for every inner game it drops (nothing else gives them back). ``release_channels`` (shutdown)
forgets the declaration.

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
the mixer: a silent tile's sound must not be heard, and it holds no heard set. The table asks
the audio route of the context it was made in (its audio engine's, made and installed in that
context), not the current one, so a handle used from another context still follows its own
context's route. While that context is silent (or, for an inner context, holds no heard set)
the table makes no mixer call (``play``, ``fadeout``, ``stop``, ``pause``, ``unpause``,
``set_volume``) and reads every channel as idle (``get_busy`` is never asked): its voices, their
ends, steals, delayed plays and ``is_playing`` go on by frame time exactly as heard, since none
of them was ever decided by the device. Each slot remembers whether its voice (or fade) reached
the mixer (``_Slot.heard``), and only such a slot's channel is touched, and only while the
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
from pydantic import BaseModel, ConfigDict

from glitchygames.audio.route import AUDIO_ROUTE_SLOT
from glitchygames.engine_context import ContextSlot, current_context
from glitchygames.render_target import is_inner_context

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
# The debug panel's name for the voice table's own channels (ChannelState.group)
LIBRARY_GROUP = 'library'

# The last partition's mixer: its channel count afterwards and the channels it reserved, which
# reserved_channel_count reads back
_partitioned_mixer: dict[str, int] = {}

# Arcade sub-plan 4, decision 4: two heard sets of library channels, alternating between the
# heard inner games, and a live-voice pool per inner game
HEARD_SET_COUNT = 2
DEFAULT_HEARD_SET_CHANNELS = 32
DEFAULT_LIVE_CHANNELS_PER_INNER_GAME = 4
RESERVE_INNER_GAME_CHANNELS_CALL = 'glitchygames.audio.reserve_inner_game_channels(games=...)'


class _InnerGameChannels:
    """The inner games' channels on the mixer, as the host declared them (the module docstring).

    A plain class, not a frozen model: it is changed in place. The heard sets and the live
    pools lie in ``base .. top-1``, reserved. Each heard set and each live pool is held by one
    inner context's holder (``_InnerChannelsHolder``) or by none. The declaration belongs to the
    mixer whose channel count it saw: a restarted mixer has none, and ``generation`` moves each
    time it is forgotten, so a holder from before never gives anything back into a new one.

    Attributes:
        channel_count: The mixer's channel count after the declaration.
        base: The first channel of the first heard set (the default partition's reservation).
        top: One past the last live pool's last channel (the reservation covers ``0 .. top-1``).
        heard_set_channels: The channels in each heard set.
        live_channels_per_game: The channels in each live pool.
        heard_set_holders: Each heard set's holder, or None while free.
        heard_set_releases: When each heard set was last given back (a running count).
        live_pool_holders: Each live pool's holder, or None while free.
        releases: The running count of heard-set releases.
        generation: Moves each time the declaration is forgotten.

    """

    def __init__(self) -> None:
        """Start with nothing declared."""
        self.channel_count = 0
        self.base = 0
        self.top = 0
        self.heard_set_channels = 0
        self.live_channels_per_game = 0
        self.heard_set_holders: list[_InnerChannelsHolder | None] = []
        self.heard_set_releases: list[int] = []
        self.live_pool_holders: list[_InnerChannelsHolder | None] = []
        self.releases = 0
        self.generation = 0

    def forget(self) -> None:
        """Forget the declaration: nothing declared, and nothing from before is given back."""
        self.channel_count = 0
        self.base = 0
        self.top = 0
        self.heard_set_channels = 0
        self.live_channels_per_game = 0
        self.heard_set_holders = []
        self.heard_set_releases = []
        self.live_pool_holders = []
        self.generation += 1

    def holds_anything(self) -> bool:
        """Whether an inner context holds a heard set or a live pool.

        Returns:
            True while one does.
        """
        return any(holder is not None for holder in self.heard_set_holders) or any(
            holder is not None for holder in self.live_pool_holders
        )

    def heard_set_start(self, *, index: int) -> int:
        """The first channel of a heard set.

        Args:
            index: The heard set (0 or 1).

        Returns:
            The channel index.
        """
        return self.base + index * self.heard_set_channels

    def live_pool_channels(self, *, index: int) -> tuple[int, ...]:
        """A live pool's channels.

        Args:
            index: The live pool (one per inner game).

        Returns:
            The channel indices.
        """
        start = self.base + HEARD_SET_COUNT * self.heard_set_channels
        start += index * self.live_channels_per_game
        return tuple(range(start, start + self.live_channels_per_game))


class _EveryChannelReservation:
    """Whether ``every_channel_reserved`` is in force, and how deeply nested.

    A plain class, not a frozen model: it is changed in place.

    Attributes:
        depth: The nesting depth; 0 when not in force.

    """

    def __init__(self) -> None:
        """Start not in force."""
        self.depth = 0


_inner_game_channels = _InnerGameChannels()
_every_channel_reservation = _EveryChannelReservation()


@dataclasses.dataclass(frozen=True, slots=True)
class ChannelPartition:
    """Which mixer channels belong to whom (impl spec 7.1).

    Attributes:
        live: The live voices' channel indices.
        library: The voice table's channel indices; for an inner context its logical slots
            (``0 .. n-1``), played on the heard set it holds while heard.
        legacy_count: The unreserved channels left for ``Sound.play()`` callers.
        plays_on_a_heard_set: True for an inner context's partition (the module docstring).
    """

    live: tuple[int, ...]
    library: tuple[int, ...]
    legacy_count: int
    plays_on_a_heard_set: bool = False


class InnerGameChannelLayout(BaseModel):
    """Where ``reserve_inner_game_channels`` put the inner games' channels (read-only).

    Attributes:
        heard_sets: Each heard set's channels.
        live_pools: Each inner game's live pool's channels.
        legacy_count: The unreserved channels left for ``Sound.play()`` callers, above them all.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    heard_sets: tuple[tuple[int, ...], ...]
    live_pools: tuple[tuple[int, ...], ...]
    legacy_count: int


class ChannelsHeldError(RuntimeError):
    """Inner games hold channels that a new partition or declaration would move.

    A host finishes every inner game (``InnerGame.finish``) before it declares the inner games'
    channels again or a new outer engine partitions the mixer, then declares them again.
    """


class InnerGameChannelsError(RuntimeError):
    """An inner game cannot have the channels it asks for (it fails alone; the message says why)."""


class MixerBusyError(RuntimeError):
    """The mixer would grow while a channel plays (BUGS.md #145).

    ``set_num_channels`` reallocates pygame's channel table without SDL's audio lock, so a
    partition that must grow the mixer is made before anything plays (at the engine's start).
    """


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


def inner_game_channels_declared() -> bool:
    """Whether inner games' channels are declared on the running mixer.

    Returns:
        True after ``reserve_inner_game_channels`` (or a host engine's ``INNER_GAMES``), until a
        restart, ``release_channels`` or a larger outer partition forgets it.
    """
    return _declared_inner_game_channels() is not None


def _declared_inner_game_channels() -> _InnerGameChannels | None:
    """The inner games' channels, when declared on the running mixer.

    Returns:
        The declaration, or None without a mixer, before one, or after a restart.
    """
    declaration = _inner_game_channels
    if pygame.mixer.get_init() is None or declaration.top == 0:
        return None
    if declaration.channel_count != pygame.mixer.get_num_channels():
        return None
    return declaration


def _logical_reserved_count() -> int:
    """The channels that are reserved outside ``every_channel_reserved``.

    Returns:
        The default partition's reserved channels, or the declared inner games' top when higher.
    """
    declaration = _declared_inner_game_channels()
    return max(reserved_channel_count(), 0 if declaration is None else declaration.top)


def _apply_the_reservation() -> None:
    """Reserve what should be: every channel while ``every_channel_reserved`` is in force."""
    if _every_channel_reservation.depth > 0:
        pygame.mixer.set_reserved(pygame.mixer.get_num_channels())
    else:
        pygame.mixer.set_reserved(_logical_reserved_count())


def inner_game_channel_count(
    *,
    games: int,
    heard_set_channels: int = DEFAULT_HEARD_SET_CHANNELS,
    live_channels_per_game: int = DEFAULT_LIVE_CHANNELS_PER_INNER_GAME,
) -> int:
    """The channels a declaration of ``games`` inner games lays out (decision 4).

    Args:
        games: How many inner games run at once.
        heard_set_channels: Library channels in each heard set.
        live_channels_per_game: Live-voice channels per inner game.

    Returns:
        Two heard sets plus a live pool per game.
    """
    return HEARD_SET_COUNT * heard_set_channels + games * live_channels_per_game


def reserve_channels(
    *, live_pool: int, library_channels: int, legacy_channels: int, inner_games: int = 0
) -> ChannelPartition:
    """Partition the mixer's channels; call once at startup before any sound plays.

    Sets the channel count to ``live_pool + library_channels + legacy_channels`` and reserves
    channels ``0 .. live_pool + library_channels - 1``, so ``Sound.play()`` reaches only the
    legacy channels. Nothing is playing yet, so the channels changed are idle. The inner games'
    channels declared above an earlier partition stay reserved, the legacy channels above them
    (the module docstring); while ``every_channel_reserved`` is in force every channel stays
    reserved.

    With ``inner_games`` (a host's ``Scene.INNER_GAMES``, read by
    ``GameEngine.reserved_channel_partition``) the inner games' channels are declared too, the
    default sizes, in the same one growth: the partition and the declaration are made at the
    engine's construction, before anything plays (``reserve_inner_game_channels``).

    A partition that covers channels declared for inner games with none held forgets the
    declaration (a new outer engine after an earlier host's), with a warning naming it: the
    host declares again, above this partition. One that would cover them while an inner game
    holds some (a new outer engine while inner games run), or declare its own while one does,
    raises ``ChannelsHeldError`` (``_declaration_kept_by_a_partition``).

    Args:
        live_pool: Channels for live voices (``--live-voice-pool``).
        library_channels: Channels for the voice table (``--sound-channels``).
        legacy_channels: Unreserved channels for ``Sound.play()`` (pygame's default is 8).
        inner_games: The inner games to declare channels for (0: none).

    Returns:
        The partition (empty without a mixer).

    Raises:
        MixerBusyError: If the mixer must grow while a channel plays (BUGS.md #145); nothing is
            changed.
    """
    _check_channel_counts(
        live_pool=live_pool,
        library_channels=library_channels,
        legacy_channels=legacy_channels,
        inner_games=inner_games,
    )
    if pygame.mixer.get_init() is None:
        return ChannelPartition(live=(), library=(), legacy_count=0)
    requested_count = live_pool + library_channels
    declaration, covered_declaration = _declaration_kept_by_a_partition(
        requested_count=requested_count, inner_games=inner_games
    )
    top = 0 if declaration is None else declaration.top
    if inner_games > 0:
        top = max(top, requested_count + inner_game_channel_count(games=inner_games))
    total_channels = max(requested_count, top) + legacy_channels
    # The channel table only grows. A second engine in one process (a test run, a launcher)
    # finds the count it set already there: changing it again would be needless, and every
    # set_num_channels reallocates pygame's channel table while the audio thread may still finish
    # a sound on it (BUGS.md #145), so a growth while a channel plays is refused. A smaller count
    # would also stop sounds on the removed channels (pygame-ce 2.5.8). A restarted mixer is back
    # at its default count, so it grows again.
    grows = pygame.mixer.get_num_channels() < total_channels
    if grows and pygame.mixer.get_busy():
        message = (
            f'the partition must grow the mixer to {total_channels} channels while a channel '
            "plays, which corrupts pygame's channel table (BUGS.md #145): partition before "
            'anything plays (the engine does as its event managers are made, in start())'
        )
        raise MixerBusyError(message)
    if covered_declaration is not None:
        log.warning(
            "A partition of channels 0-%d covers the inner games' channels declared from "
            'channel %d: the declaration is forgotten; declare them again (%s)',
            requested_count - 1,
            covered_declaration.base,
            RESERVE_INNER_GAME_CHANNELS_CALL,
        )
        _inner_game_channels.forget()
    if grows:
        pygame.mixer.set_num_channels(total_channels)
    channel_count = pygame.mixer.get_num_channels()
    reserved_count = min(requested_count, channel_count)
    _partitioned_mixer.clear()
    _partitioned_mixer.update(channel_count=channel_count, reserved_count=reserved_count)
    if declaration is not None:
        declaration.channel_count = channel_count
    if inner_games > 0:
        # Inside the mixer just grown: no second growth
        _lay_out_inner_game_channels(
            games=inner_games,
            heard_set_channels=DEFAULT_HEARD_SET_CHANNELS,
            live_channels_per_game=DEFAULT_LIVE_CHANNELS_PER_INNER_GAME,
            legacy_count=legacy_channels,
        )
    _apply_the_reservation()
    return ChannelPartition(
        live=tuple(range(min(live_pool, reserved_count))),
        library=tuple(range(live_pool, reserved_count)),
        legacy_count=channel_count - _logical_reserved_count(),
    )


def _declaration_kept_by_a_partition(
    *, requested_count: int, inner_games: int
) -> tuple[_InnerGameChannels | None, _InnerGameChannels | None]:
    """Which declaration a partition of ``0 .. requested_count-1`` keeps, and which it covers.

    Args:
        requested_count: The partition's reserved channels (live pool and library).
        inner_games: The inner games the partition declares too (0: none).

    Returns:
        The declaration kept (None without one, or when covered) and the one the partition
        covers with nothing held (None when none), which the caller forgets once nothing can
        refuse the partition.

    Raises:
        ChannelsHeldError: If the partition covers a declaration an inner game holds channels
            of, or declares its own while one does.
    """
    declaration = _declared_inner_game_channels()
    if declaration is not None and requested_count > declaration.base:
        if declaration.holds_anything():
            message = (
                f'the partition asks for channels 0-{requested_count - 1}, but inner games hold '
                f'channels from channel {declaration.base}: finish them first, then call '
                f'{RESERVE_INNER_GAME_CHANNELS_CALL} again'
            )
            raise ChannelsHeldError(message)
        return None, declaration
    if inner_games > 0 and declaration is not None and declaration.holds_anything():
        message = (
            'inner games hold channels of the earlier declaration: finish them before an engine '
            'declares its own'
        )
        raise ChannelsHeldError(message)
    return declaration, None


def reserve_inner_game_channels(
    *,
    games: int,
    heard_set_channels: int = DEFAULT_HEARD_SET_CHANNELS,
    live_channels_per_game: int = DEFAULT_LIVE_CHANNELS_PER_INNER_GAME,
) -> InnerGameChannelLayout:
    """Declare how many inner games the host runs: the mixer grows once, now (decision 4).

    Where to declare: a host sets ``Scene.INNER_GAMES`` on its scene class, and its engine
    declares the default sizes with its own partition at construction (the simplest); or it
    calls this after ``GameEngine(...)`` and before ``start()`` (for other sizes). Never in the
    scene's ``__init__`` or ``setup()``: those run after the CRT power-on, whose sound plays into
    frame 0. Right above the default partition (which keeps its channels) it lays out two heard
    sets of ``heard_set_channels`` library channels, then a live pool of
    ``live_channels_per_game`` channels per inner game; the mixer grows to hold them with the
    legacy channels above them all, as many as before, and the reservation is raised over
    everything below the legacy channels. Inner games then take their channels inside it, so
    the mixer never grows again: growing it while sound plays reallocates pygame's channel table
    without SDL's audio lock (BUGS.md #145), so a growth with a channel playing is refused.

    The inner games' channels lie above the outer's partition, so it is made first: when the
    current context's engine has not partitioned yet (``INNER_GAMES`` unset: it partitions as
    ``start()`` makes its event managers), this call has it partition now
    (``GameEngine.reserved_channel_partition``, with its own options), so the engine's own
    partition later finds it made and the declaration stays. Without an engine the mixer must
    already be partitioned (``glitchygames.audio.engine.default_channel_partition()``, or an
    engine's): declared on an unpartitioned mixer, the inner games' channels would start at
    channel 0, and the first partition made afterwards (an engine's start, or a scene manager's
    first ``audio``) would cover them and forget them, so the first inner game built would fail
    far from the cause. That is refused here instead.

    Declaring again is allowed only while no inner game holds a channel (finish them first);
    the mixer then only grows, never shrinks. Without a mixer nothing is declared (an inner game
    built then fails alone).

    Args:
        games: How many inner games run at once (at least 1).
        heard_set_channels: Library channels in each heard set (the largest ``--sound-channels``
            a heard inner game may have).
        live_channels_per_game: Live-voice channels per inner game (the largest
            ``--live-voice-pool`` an inner game may have).

    Returns:
        The layout (empty without a mixer).

    Raises:
        ValueError: If ``games`` is below 1 or a channel count is negative.
        ChannelsHeldError: If an inner game holds channels of an earlier declaration.
        InnerGameChannelsError: If the mixer is not partitioned and no engine can partition it
            now, or the mixer must grow for the inner games while a channel plays (BUGS.md
            #145; the engine's own partition made here first refuses that growth with
            ``MixerBusyError``).
    """
    if games < 1:
        message = f'games must be >= 1, got {games}'
        raise ValueError(message)
    _check_channel_counts(
        heard_set_channels=heard_set_channels, live_channels_per_game=live_channels_per_game
    )
    if pygame.mixer.get_init() is None:
        return InnerGameChannelLayout(heard_sets=(), live_pools=(), legacy_count=0)
    declaration = _declared_inner_game_channels()
    if declaration is not None and declaration.holds_anything():
        message = (
            'inner games hold channels of the earlier declaration: finish them before calling '
            'reserve_inner_game_channels again'
        )
        raise ChannelsHeldError(message)
    _partition_with_the_current_engine()
    if not _mixer_partitioned():
        message = (
            "the mixer is not partitioned yet, so the inner games' channels would start at "
            'channel 0, where the outer partition made later would cover and forget them: '
            'declare after GameEngine(...) (it partitions now), set Scene.INNER_GAMES on the '
            'host scene class, or partition first '
            '(glitchygames.audio.engine.default_channel_partition())'
        )
        raise InnerGameChannelsError(message)
    layout = _lay_out_inner_game_channels(
        games=games,
        heard_set_channels=heard_set_channels,
        live_channels_per_game=live_channels_per_game,
        legacy_count=pygame.mixer.get_num_channels() - _logical_reserved_count(),
    )
    _apply_the_reservation()
    return layout


def _partition_with_the_current_engine() -> None:
    """Have the current context's engine partition the mixer now, if it has not yet.

    An engine whose game sets no ``INNER_GAMES`` partitions as ``start()`` makes its event
    managers; a declaration made before that (after ``GameEngine(...)``) must lie above that
    partition, so it is made first, with the engine's own options. Nothing happens in an inner
    context (its engine never partitions), without an engine, or once it partitioned.
    """
    if is_inner_context():
        return
    # Imported here: the engine imports the audio package, which imports this module
    from glitchygames.engine.game_engine import CURRENT_ENGINE_SLOT

    engine = current_context().value(slot=CURRENT_ENGINE_SLOT).engine
    if engine is not None and engine.channel_partition is None:
        engine.reserved_channel_partition()


def _mixer_partitioned() -> bool:
    """Whether a partition was made on the running mixer (``reserve_channels``).

    Returns:
        True when the last partition's channel count is the running mixer's.
    """
    return (
        bool(_partitioned_mixer)
        and pygame.mixer.get_num_channels() == _partitioned_mixer['channel_count']
    )


def _lay_out_inner_game_channels(
    *, games: int, heard_set_channels: int, live_channels_per_game: int, legacy_count: int
) -> InnerGameChannelLayout:
    """Lay the inner games' channels out above the default partition, growing the mixer if needed.

    The reservation is the caller's to apply.

    Args:
        games: How many inner games run at once.
        heard_set_channels: Library channels in each heard set.
        live_channels_per_game: Live-voice channels per inner game.
        legacy_count: The legacy channels to keep above them.

    Returns:
        The layout.

    Raises:
        InnerGameChannelsError: If the mixer must grow while a channel plays (BUGS.md #145).
    """
    _inner_game_channels.forget()
    base = reserved_channel_count()
    top = base + inner_game_channel_count(
        games=games,
        heard_set_channels=heard_set_channels,
        live_channels_per_game=live_channels_per_game,
    )
    # The one growth: as many legacy channels as before, above everything declared
    if pygame.mixer.get_num_channels() < top + legacy_count:
        if pygame.mixer.get_busy():
            message = (
                'the mixer must grow for the inner games while a channel plays, which corrupts '
                "pygame's channel table (BUGS.md #145): declare them before anything plays, "
                'with Scene.INNER_GAMES on the host scene class or reserve_inner_game_channels '
                'after GameEngine(...) and before start(), never in setup()'
            )
            raise InnerGameChannelsError(message)
        pygame.mixer.set_num_channels(top + legacy_count)
    channel_count = pygame.mixer.get_num_channels()
    # Every caller partitioned first (reserve_channels, or a declaration on a partitioned mixer)
    _partitioned_mixer['channel_count'] = channel_count
    declared = _inner_game_channels
    declared.channel_count = channel_count
    declared.base = base
    declared.top = top
    declared.heard_set_channels = heard_set_channels
    declared.live_channels_per_game = live_channels_per_game
    declared.heard_set_holders = [None] * HEARD_SET_COUNT
    declared.heard_set_releases = [-1] * HEARD_SET_COUNT
    declared.live_pool_holders = [None] * games
    return InnerGameChannelLayout(
        heard_sets=tuple(
            tuple(
                range(
                    declared.heard_set_start(index=index),
                    declared.heard_set_start(index=index) + heard_set_channels,
                )
            )
            for index in range(HEARD_SET_COUNT)
        ),
        live_pools=tuple(declared.live_pool_channels(index=index) for index in range(games)),
        legacy_count=channel_count - top,
    )


def release_channels() -> None:
    """Give back the partition's reservation (shutdown), so a restarted mixer can play anywhere.

    SDL_mixer keeps its reservation across ``pygame.mixer.quit()`` and a new ``init()``, while the
    restarted mixer is back at 8 channels (pygame-ce 2.5.8): a ``Sound.play()`` on it would then
    land on a channel pygame does not know and raise ``IndexError: invalid channel index``. The
    inner games' declaration is forgotten with it. Nothing happens without a mixer.
    """
    _partitioned_mixer.clear()
    _inner_game_channels.forget()
    if pygame.mixer.get_init() is not None:
        pygame.mixer.set_reserved(0)


def reserved_channel_count() -> int:
    """The channels the last partition reserved on the running mixer.

    pygame cannot report its reservation, so the last partition's is remembered with the
    channel count it left; a restarted mixer is back at its default count and no longer matches.
    The inner games' channels above it are not counted.

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

    They follow the partition's own channels, or the inner games' channels above them.

    Args:
        partition: The partition (its own channels and its legacy count).

    Returns:
        ``legacy_count`` channels from the first one above the partition and the inner games'.
    """
    first_legacy = max(
        max((*partition.live, *partition.library), default=-1) + 1, _logical_reserved_count()
    )
    return range(first_legacy, first_legacy + partition.legacy_count)


@dataclasses.dataclass(slots=True)
class _InnerChannelsHolder:
    """An inner context's channels: its partition, live pool and heard set (changed in place).

    Attributes:
        partition: The context's partition, or None before its build asked (or after finish).
        live_pool_index: The live pool it holds, or None.
        heard_set_index: The heard set it holds while heard, or None.
        generation: The declaration's generation it took them in.
        plain_plays: The plain ``Sound.play()`` sounds the context started on unreserved
            channels while followed (``plain_plays_followed``), by channel, as last seen.
        sounds_at_call_start: Each unreserved channel's sound when the followed call under way
            began, or None outside one.
        context_name: The name of the context holding them (an exhausted declaration's error
            names each holder), set when its live pool is taken.
    """

    partition: ChannelPartition | None = None
    live_pool_index: int | None = None
    heard_set_index: int | None = None
    generation: int = 0
    plain_plays: dict[int, pygame.mixer.Sound] = dataclasses.field(default_factory=dict)
    sounds_at_call_start: dict[int, pygame.mixer.Sound | None] | None = None
    context_name: str = ''


# Each engine context's inner-game channels (glitchygames.engine_context; Arcade sub-plan 4,
# decision 4): only an inner context takes any (GameEngine.reserved_channel_partition)
INNER_CHANNELS_SLOT: ContextSlot[_InnerChannelsHolder] = ContextSlot(
    name='glitchygames.audio.voices.inner_channels', factory=_InnerChannelsHolder
)


def _current_declaration_for(holder: _InnerChannelsHolder) -> _InnerGameChannels | None:
    """The declaration a holder's channels belong to, if it is still the running one.

    Returns:
        The declaration, or None when none runs or the holder's is from before.
    """
    declaration = _declared_inner_game_channels()
    if declaration is None or holder.generation != declaration.generation:
        return None
    return declaration


def inner_context_partition(*, live_pool: int, library_channels: int) -> ChannelPartition:
    """The current (inner) context's partition, its live pool taken on the first call.

    An inner context never partitions the mixer (decisions 4 and 5): its voice table has
    ``library_channels`` logical slots (its recording's ``--sound-channels``), played on a heard
    set only while it is heard, and its live voices take a free live pool's first ``live_pool``
    channels. A later call returns the same partition, whatever it asks for. Without a mixer the
    empty partition is returned and nothing is kept.

    Args:
        live_pool: The live voices' channels (the context's ``--live-voice-pool``).
        library_channels: The voice table's slots (the context's ``--sound-channels``).

    Returns:
        The partition.

    Raises:
        InnerGameChannelsError: With no inner games' channels declared, with every live pool
            held (more inner games than declared), or for a live pool larger than declared (a
            smaller one would make a ``create_voice`` the game made alone fail, so the inner game
            fails at once instead).
    """
    _check_channel_counts(live_pool=live_pool, library_channels=library_channels)
    if pygame.mixer.get_init() is None:
        return ChannelPartition(live=(), library=(), legacy_count=0)
    holder = current_context().value(slot=INNER_CHANNELS_SLOT)
    if holder.partition is not None and _current_declaration_for(holder) is not None:
        return holder.partition
    declaration = _declared_inner_game_channels()
    if declaration is None:
        message = (
            f'no channels are declared for inner games: the host calls '
            f'{RESERVE_INNER_GAME_CHANNELS_CALL} once at startup, before building them'
        )
        raise InnerGameChannelsError(message)
    if live_pool > declaration.live_channels_per_game:
        message = (
            f'--live-voice-pool {live_pool} is more than the '
            f'{declaration.live_channels_per_game} live channels declared per inner game: '
            f'declare more (glitchygames.audio.reserve_inner_game_channels(games=..., '
            f'live_channels_per_game=...))'
        )
        raise InnerGameChannelsError(message)
    free_pools = [
        index
        for index, pool_holder in enumerate(declaration.live_pool_holders)
        if pool_holder is None
    ]
    if not free_pools:
        holder_names = ', '.join(
            repr(pool_holder.context_name)
            for pool_holder in declaration.live_pool_holders
            if pool_holder is not None
        )
        message = (
            f'all {len(declaration.live_pool_holders)} inner games declared are running '
            f'({holder_names}): finish one (InnerGame.finish(), also for one the host dropped), '
            f'or declare more ({RESERVE_INNER_GAME_CHANNELS_CALL})'
        )
        raise InnerGameChannelsError(message)
    pool_index = free_pools[0]
    declaration.live_pool_holders[pool_index] = holder
    holder.context_name = current_context().name
    partition = ChannelPartition(
        live=declaration.live_pool_channels(index=pool_index)[:live_pool],
        library=tuple(range(library_channels)),
        legacy_count=pygame.mixer.get_num_channels() - declaration.top,
        plays_on_a_heard_set=True,
    )
    holder.partition = partition
    holder.live_pool_index = pool_index
    holder.heard_set_index = None
    holder.generation = declaration.generation
    return partition


def take_heard_set() -> None:
    """Give the current (inner) context a heard set to play on: it is being made heard.

    The heard sets alternate: the free set given back longest ago is taken, so a new heard game
    starts on the other set while the one it replaces fades out on its own (the 50 ms of going
    silent). A set still sounding when taken (heard games switched faster than that fade) is
    stopped first, so the new game starts on quiet channels: a hard stop, which may click (a known
    limit: SDL_mixer ignores a second fadeout on a channel already fading, so the remaining fade
    cannot be shortened). Holding one already: nothing.

    Raises:
        InnerGameChannelsError: Without the context's partition (never built, finished, or from
            before a restart), when its slots outnumber a heard set's channels (it replays
            silent but cannot be heard), or when both sets are held (two inner games heard).
    """
    holder = current_context().value(slot=INNER_CHANNELS_SLOT)
    declaration = _current_declaration_for(holder)
    if holder.partition is None or declaration is None:
        message = 'the inner game holds no channels (never built, or finished): it cannot be heard'
        raise InnerGameChannelsError(message)
    if holder.heard_set_index is not None:
        return
    slot_count = len(holder.partition.library)
    if slot_count > declaration.heard_set_channels:
        message = (
            f'--sound-channels {slot_count} is more than a heard set'
            f"'s {declaration.heard_set_channels} channels: the inner game replays silent and "
            f'cannot be heard'
        )
        raise InnerGameChannelsError(message)
    free_sets = [
        index
        for index, set_holder in enumerate(declaration.heard_set_holders)
        if set_holder is None
    ]
    if not free_sets:
        message = 'two inner games are heard already: make one silent first'
        raise InnerGameChannelsError(message)
    set_index = min(free_sets, key=lambda index: declaration.heard_set_releases[index])
    start = declaration.heard_set_start(index=set_index)
    for channel_index in range(start, start + declaration.heard_set_channels):
        channel = pygame.mixer.Channel(channel_index)
        if channel.get_busy():
            channel.stop()
    declaration.heard_set_holders[set_index] = holder
    holder.heard_set_index = set_index


def give_back_heard_set() -> None:
    """The current (inner) context is no longer heard: its heard set is free (still fading)."""
    holder = current_context().value(slot=INNER_CHANNELS_SLOT)
    set_index = holder.heard_set_index
    holder.heard_set_index = None
    declaration = _current_declaration_for(holder)
    if set_index is None or declaration is None:
        return
    declaration.heard_set_holders[set_index] = None
    declaration.heard_set_releases[set_index] = declaration.releases
    declaration.releases += 1


def heard_set_start() -> int | None:
    """The first channel of the heard set the current context holds.

    Returns:
        The channel index, or None while it holds none (silent, or not an inner context).
    """
    return _heard_set_start_for(current_context().value(slot=INNER_CHANNELS_SLOT))


def _heard_set_start_for(holder: _InnerChannelsHolder) -> int | None:
    """The first channel of the heard set a context's holder holds.

    Returns:
        The channel index, or None while it holds none.
    """
    declaration = _current_declaration_for(holder)
    if holder.heard_set_index is None or declaration is None:
        return None
    return declaration.heard_set_start(index=holder.heard_set_index)


def release_inner_context_channels() -> None:
    """Give back the current (inner) context's heard set and live pool (``InnerGame.finish``).

    The live pool's channels are stopped (twice: a stop starts a queued chunk, as in
    ``glitchygames.audio.live``), so a voice left on them never sounds into the next game's: a
    hard stop, which may click when the game was heard (a known limit: a live voice's fade is
    rendered into chunks over frames, which a finished game no longer runs).
    Nothing happens for a context holding none.
    """
    give_back_heard_set()
    holder = current_context().value(slot=INNER_CHANNELS_SLOT)
    partition = holder.partition
    pool_index = holder.live_pool_index
    # Going silent stopped them (stop_plain_plays_and_mute_the_live_pool): nothing to follow
    holder.plain_plays = {}
    holder.partition = None
    holder.live_pool_index = None
    declaration = _current_declaration_for(holder)
    if partition is None or pool_index is None or declaration is None:
        return
    for channel_index in partition.live:
        channel = pygame.mixer.Channel(channel_index)
        channel.stop()
        channel.stop()
    declaration.live_pool_holders[pool_index] = None


def unreserved_channel_indices() -> range:
    """The channels a plain ``Sound.play()`` may land on: every one above the reservation.

    Read outside ``every_channel_reserved`` (which only borrows them): above the default
    partition's reservation, or the declared inner games' channels when higher.

    Returns:
        The channel indices (empty without a mixer).
    """
    if pygame.mixer.get_init() is None:
        return range(0)
    return range(_logical_reserved_count(), pygame.mixer.get_num_channels())


def _sounds_on(*, channel_indices: range) -> dict[int, pygame.mixer.Sound | None]:
    """Each channel's sound now (``Channel.get_sound``: None while it plays nothing).

    Args:
        channel_indices: The channels to read.

    Returns:
        Each channel's sound, by channel.
    """
    return {
        channel_index: pygame.mixer.Channel(channel_index).get_sound()
        for channel_index in channel_indices
    }


def _plain_play_sounds(holder: _InnerChannelsHolder) -> dict[int, pygame.mixer.Sound]:
    """The plain plays a context started that still play (the ``plain_plays_followed`` rules).

    A followed one counts while its channel still plays that very sound (``get_sound`` is it):
    once it ended, the channel may play another context's sound, which is never counted. In a
    followed call under way, a channel playing another sound than when the call began counts
    too: only that context ran since.

    Args:
        holder: The context's holder.

    Returns:
        Each such sound, by channel (empty without a mixer).
    """
    if pygame.mixer.get_init() is None:
        return {}
    channel_count = pygame.mixer.get_num_channels()
    sounds = {
        channel_index: sound
        for channel_index, sound in holder.plain_plays.items()
        if channel_index < channel_count
        and pygame.mixer.Channel(channel_index).get_sound() is sound
    }
    sounds_at_call_start = holder.sounds_at_call_start
    if sounds_at_call_start is not None:
        sounds.update(
            (channel_index, sound)
            for channel_index, sound in _sounds_on(
                channel_indices=unreserved_channel_indices()
            ).items()
            if sound is not None and sound is not sounds_at_call_start.get(channel_index)
        )
    return sounds


@contextlib.contextmanager
def plain_plays_followed() -> Generator[None]:
    """Follow the plain ``Sound.play()`` sounds the current context starts in the body.

    An audible inner game's build, steps and finish run inside it (``InnerGame``; Arcade
    sub-plan 4, decision 6), so when it goes silent its plain plays still sounding are stopped
    (``stop_plain_plays_and_mute_the_live_pool``) and no other context's are. pygame cannot say
    who started a sound, so the body's are told apart by their channels: an unreserved channel
    playing another sound after the body than before it was started by the body (a plain play
    only ever takes a free channel; the host's code does not run inside it). Kept by channel
    with the very sound object, so a channel whose followed sound ended and that now plays
    another context's sound is never taken for this one's.

    A context that went silent inside the body (a finish, which makes it silent) has its plain
    plays stopped then; a plain play the body started after that is stopped as the body ends,
    since nothing would stop it later.

    One edge pygame cannot tell apart: a ``Sound`` object shared by two audible contexts (the
    host and its heard game, or two heard games at once). When this context's
    followed play of it ends and the other context plays the same object on the channel it
    left, the channel still plays "that very sound", so it is taken for this context's play and
    stopped when this context goes silent. Only one shared object played plain is affected
    (each game loads its own sounds, and the engine's shared samples play on the voice table).

    Yields:
        Nothing; the body's plain plays are followed.
    """
    holder = current_context().value(slot=INNER_CHANNELS_SLOT)
    holder.sounds_at_call_start = _sounds_on(channel_indices=unreserved_channel_indices())
    try:
        yield
    finally:
        holder.plain_plays = _plain_play_sounds(holder)
        holder.sounds_at_call_start = None
        if not current_context().value(slot=AUDIO_ROUTE_SLOT).audible:
            # Started after the context went silent in the body: never heard past it
            for channel_index in holder.plain_plays:
                pygame.mixer.Channel(channel_index).stop()
            holder.plain_plays = {}


def plain_play_channel_indices() -> tuple[int, ...]:
    """The unreserved channels playing a plain play the current context started (followed).

    Returns:
        The channel indices, lowest first (empty when it started none, or none still plays).
    """
    holder = current_context().value(slot=INNER_CHANNELS_SLOT)
    return tuple(sorted(_plain_play_sounds(holder)))


def stop_plain_plays_and_mute_the_live_pool() -> None:
    """Take the current (inner) context's sound off the mixer now: it is going silent.

    Decision 6 (Arcade sub-plan 4): its plain plays still sounding on unreserved channels
    (followed: ``plain_plays_followed``) are stopped, and the live-voice chunks playing or
    queued on its live pool are set to volume 0 (its later chunks are rendered at volume 0:
    glitchygames.audio.live), so nothing of it is heard after the switch. Hard cuts, which may
    click (a known limit, as the heard set's stop in ``take_heard_set``). Only the context's
    own sounds and channels are touched: another context's sound on a channel is never stopped.
    The voices' lifecycle reads only its channels' busy and queue state, never a volume, so
    what the game sees is unchanged. Nothing happens without a mixer.
    """
    holder = current_context().value(slot=INNER_CHANNELS_SLOT)
    for channel_index in _plain_play_sounds(holder):
        pygame.mixer.Channel(channel_index).stop()
    holder.plain_plays = {}
    if holder.partition is None or _current_declaration_for(holder) is None:
        return
    for channel_index in holder.partition.live:
        channel = pygame.mixer.Channel(channel_index)
        # The queue first: a chunk ending between the two reads moves the queued one to playing,
        # which the second read then finds (read the other way, it would be missed at volume 1)
        queued_chunk = channel.get_queue()
        playing_chunk = channel.get_sound()
        for chunk in (playing_chunk, queued_chunk):
            if chunk is not None:
                chunk.set_volume(0.0)


def current_inner_context_channel_indices() -> tuple[int, ...]:
    """Every channel the current (inner) context's sound may be on right now.

    Its heard set while it holds one, its live pool, and the unreserved channels playing its
    plain plays (``plain_play_channel_indices``); never another context's channel. What a
    ``FrameSilencer`` in an inner context may stop.

    Returns:
        The channel indices, lowest first (empty without a mixer or channels).
    """
    holder = current_context().value(slot=INNER_CHANNELS_SLOT)
    channel_indices = set(_plain_play_sounds(holder))
    declaration = _current_declaration_for(holder)
    if holder.partition is not None and declaration is not None:
        channel_indices.update(holder.partition.live)
        start = _heard_set_start_for(holder)
        if start is not None:
            channel_indices.update(range(start, start + declaration.heard_set_channels))
    return tuple(sorted(channel_indices))


@contextlib.contextmanager
def every_channel_reserved() -> Generator[None]:
    """Reserve every mixer channel for the body, then put the reservation back as it was.

    With every channel reserved, SDL finds no channel for a plain ``Sound.play()``, which then
    returns None and starts nothing, as on a busy mixer; an explicit ``Channel(index).play()``
    still plays. A silent inner game's build, steps and finish run inside it (Arcade sub-plan 4,
    decision 2), so its plain plays reach no channel and take none from the heard game.

    pygame cannot report its reservation, so the one put back is the last partition's
    (``reserved_channel_count``, read before) with the inner games' declared channels above it,
    on the mixer's channel count afterwards: a partition made inside neither keeps its
    reservation nor is remembered, and a mixer grown inside keeps the reservation from before.
    A nested call (one silent game's call inside another's) only runs its body: the outermost
    puts the reservation back. Without a mixer before or after the body, nothing is reserved or
    put back. The body's exceptions propagate, the reservation put back first.

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
        the mixer (see the module docstring). An inner context's table (its partition plays on a
        heard set) plays its slots on the heard set that context holds, and only while it holds
        one.

        Args:
            partition: The channel partition (``reserve_channels``, or
                ``inner_context_partition``).
            buses: The bus tree whose gains and reservations apply.
            compile_for_play: The library's ``compile_for_play``, called on every play.
        """
        self._audio_route = current_context().value(slot=AUDIO_ROUTE_SLOT)
        self._inner_channels = (
            current_context().value(slot=INNER_CHANNELS_SLOT)
            if partition.plays_on_a_heard_set
            else None
        )
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
        # Frames (advances) run so far, and the frame of each channel's latest steal, by the index
        # the snapshot shows (an inner table's: in its heard set, or its logical slot); a few
        # entries per library slot at most, so it stays bounded (the debug panel's steal flash)
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
        """Whether the table's context is audible, so its heard slots' channels are touched.

        An inner context's table also needs a heard set (``take_heard_set``).
        """
        if not self._audio_route.audible:
            return False
        return (
            self._inner_channels is None or _heard_set_start_for(self._inner_channels) is not None
        )

    def _mixer_channel(self, slot: _Slot) -> int | None:
        """The mixer channel a slot plays on now.

        Returns:
            The slot's own channel; for an inner context's table, the slot's channel in the
            heard set its context holds, or None while it holds none.
        """
        if self._inner_channels is None:
            return slot.channel_index
        start = _heard_set_start_for(self._inner_channels)
        return None if start is None else start + slot.number

    def _channel(self, slot: _Slot) -> pygame.mixer.Channel:
        """The mixer channel of a slot the table may touch (``_sounds`` said so).

        Returns:
            The channel.
        """
        index = self._mixer_channel(slot)
        assert index is not None  # a table reaching the mixer holds its heard set
        return pygame.mixer.Channel(index)

    def _shown_index(self, slot: _Slot) -> int:
        """The channel index the debug panel shows for a slot.

        Returns:
            Its mixer channel, or its logical slot while an inner table holds no heard set.
        """
        index = self._mixer_channel(slot)
        return slot.channel_index if index is None else index

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
            self._channel(slot).pause()
        slot.state = _SlotState.PAUSED

    def _resume(self, slot: _Slot, voice: _Voice) -> None:
        """Let a held voice play on: its channel unpauses (when heard) and a release fades."""
        if self._sounds(slot):
            self._channel(slot).unpause()
        slot.state = _SlotState.PLAYING
        self._fade_out_release(slot, voice)

    def silenced(self, channel_index: int | None) -> None:
        """A channel was stopped outside the table (``FrameSilencer``): only the channel is quiet.

        The slot's voice (or fade) stays in the table with its generation and played time, so
        what the game sees is what it saw in the run that was not silenced (impl spec 7.3); the
        slot is marked device-stopped until its channel's next play.

        Args:
            channel_index: The mixer channel (channels the table does not play on are
                ignored), or None after ``pygame.mixer.stop()``: every channel.
        """
        for slot in self._slots:
            if slot.state is _SlotState.IDLE:
                continue
            if channel_index is None or self._mixer_channel(slot) == channel_index:
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
            channel = self._channel(slot)
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
                index=self._shown_index(slot),
                group=LIBRARY_GROUP,
                state='idle' if slot.device_stopped else _SNAPSHOT_STATE[slot.state],
            )
            for slot in self._slots
        )
        # Above the partition and the inner games' declared channels (an inner table's library
        # slots are logical, below its live pool, so the snapshot is sorted by index)
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
                if not self._channel(slot).get_busy():
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
            order = (not voice.releasing, voice.priority, voice.play_number, slot.number)
            candidates.append((order, slot))
        if not candidates:
            return None
        return min(candidates, key=operator.itemgetter(0))[1]

    def _steal(self, slot: _Slot) -> None:
        """Fade a playing voice over 10 ms (when heard) and end it; its channel is fading."""
        if self._sounds(slot):
            self._channel(slot).fadeout(STEAL_FADE_MILLISECONDS)
        self._fade_slot(slot, fade_seconds=STEAL_FADE_MILLISECONDS / MILLISECONDS_PER_SECOND)
        self._steals += 1
        self._steal_frames[self._shown_index(slot)] = self._frames_advanced

    def _start(self, slot: _Slot, voice: _Voice) -> None:
        """Play a voice on its channel, then set its gains (pygame resets volume on play).

        In a silent context the voice starts in the table only, unheard for its whole life.
        """
        slot.heard = self.reaches_the_mixer
        if slot.heard:
            channel = self._channel(slot)
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
                self._channel(slot).stop()
            self._end_voice(slot)
        else:
            seconds = max(fade_seconds, MINIMUM_FADE_SECONDS)
            if self._sounds(slot):
                self._channel(slot).fadeout(round(seconds * MILLISECONDS_PER_SECOND))
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
            self._channel(slot).fadeout(round(remaining * MILLISECONDS_PER_SECOND))

    def _apply_gains(self, slot: _Slot, voice: _Voice) -> None:
        """Set the channel's left and right gains from the voice and its bus (impl spec 7.2)."""
        if slot.state is _SlotState.WAITING or not self._sounds(slot):
            return  # applied when it starts; an unheard channel is never touched
        gain = voice.volume * self._buses[voice.bus].effective_gain()
        left, right = constant_power_gains(pan=voice.pan, gain=gain)
        self._channel(slot).set_volume(left, right)

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
