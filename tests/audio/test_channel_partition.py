"""Tests for the live/library/legacy channel partition (impl spec 7.1, AUD-MIX-008)."""

import contextlib
import logging
from typing import ClassVar

import pygame
import pytest

from glitchygames.audio.engine import default_channel_partition
from glitchygames.audio.instrument import Instrument
from glitchygames.audio.live import LiveAudio
from glitchygames.audio.route import set_audible
from glitchygames.audio.voices import (
    INNER_CHANNELS_SLOT,
    ChannelPartition,
    ChannelsHeldError,
    InnerGameChannelLayout,
    InnerGameChannelsError,
    MixerBusyError,
    SoundHandle,
    VoiceCounters,
    VoiceTable,
    current_inner_context_channel_indices,
    every_channel_reserved,
    give_back_heard_set,
    heard_set_start,
    inner_context_partition,
    inner_game_channels_declared,
    plain_play_channel_indices,
    plain_plays_followed,
    release_channels,
    release_inner_context_channels,
    reserve_channels,
    reserve_inner_game_channels,
    reserved_channel_count,
    take_heard_set,
    unreserved_channel_indices,
)
from glitchygames.engine_context import EngineContext
from glitchygames.render_target import set_render_target
from glitchygames.replay.silence import FrameSilencer
from tests.audio.library_support import start_mixer, stop_mixer
from tests.audio.voice_support import (
    FRAME_SECONDS,
    GAME_SCENE,
    PLAY_DEFAULTS,
    RecordingChannel,
    advance_frames,
    baked_sound,
    make_table,
    start_reserved_mixer,
    unreserved_buses,
    unreserved_channel_ids,
)


@pytest.fixture(autouse=True)
def _mixer_stopped_afterwards():
    """Stop the mixer after each test so the harness restarts it with the run's format."""
    yield
    stop_mixer()


def test_the_partition_is_live_then_library_then_legacy():
    """4 + 32 + 8 channels: 0-3 live, 4-35 library, the last 8 for legacy plays."""
    partition = start_reserved_mixer()

    assert partition == ChannelPartition(
        live=(0, 1, 2, 3), library=tuple(range(4, 36)), legacy_count=8
    )
    assert pygame.mixer.get_num_channels() == 44


def test_legacy_plays_land_only_on_the_unreserved_channels():
    """Sound.play() picks among channels 36-43 only, and a ninth finds none free."""
    start_reserved_mixer()
    legacy_sound = pygame.mixer.Sound(buffer=bytes(44100 * 4))

    channels = [legacy_sound.play() for _ in range(8)]
    ninth = legacy_sound.play()

    assert sorted(channel.id for channel in channels) == list(range(36, 44))
    assert ninth is None


def test_library_and_legacy_plays_never_cut_each_other():
    """AUD-MIX-008: a full library and a full legacy set play side by side."""
    partition = start_reserved_mixer()
    table = make_table(partition)
    short_sound = baked_sound(seconds=0.5)
    legacy_sound = pygame.mixer.Sound(buffer=bytes(44100 * 4))

    # 36 effects plays take the 28 channels the ui and music reservations leave and steal 8 of
    # them; the ui and music plays then take their reserved channels: 32 voices in all
    handles = [table.play(short_sound, owner=GAME_SCENE, **PLAY_DEFAULTS) for _ in range(36)]
    for bus, priority in (('ui', 80), ('ui', 80), ('music', 90), ('music', 90)):
        handles.append(
            table.play(
                short_sound,
                owner=GAME_SCENE,
                **(PLAY_DEFAULTS | {'bus': bus, 'priority': priority}),
            )
        )
    legacy_channels = [legacy_sound.play() for _ in range(8)]

    assert all(channel is not None and channel.get_busy() for channel in legacy_channels)
    assert sum(handle.is_playing for handle in handles) == 32
    table.advance(dt=1 / 60, paused_owners=frozenset())
    assert all(channel.get_busy() for channel in legacy_channels)
    library_busy = [pygame.mixer.Channel(index).get_busy() for index in partition.library]
    assert all(library_busy)


def test_reserving_again_on_the_same_mixer_leaves_the_channel_count_alone(mocker):
    """BUGS.md #145: a second engine in one process never reallocates the channel table."""
    start_reserved_mixer()
    set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

    partition = reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)

    assert partition.library == tuple(range(4, 36))
    set_num_channels.assert_not_called()
    assert pygame.mixer.get_num_channels() == 44


def test_a_second_smaller_partition_never_shrinks_the_mixer(mocker):
    """BUGS.md #145: the channel table only grows; a smaller partition keeps the count."""
    start_reserved_mixer()
    set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

    partition = reserve_channels(live_pool=2, library_channels=4, legacy_channels=2)

    set_num_channels.assert_not_called()
    assert pygame.mixer.get_num_channels() == 44
    assert partition == ChannelPartition(live=(0, 1), library=(2, 3, 4, 5), legacy_count=38)


def test_a_restarted_mixer_is_partitioned_again():
    """A restarted mixer is back at its default count, so it is grown again."""
    start_reserved_mixer()
    start_mixer(channels=2)
    restarted_count = pygame.mixer.get_num_channels()

    reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)

    assert restarted_count == 8
    assert pygame.mixer.get_num_channels() == 44


def test_without_a_mixer_nothing_is_reserved():
    """No mixer: an empty partition, so every library play is silent."""
    stop_mixer()

    partition = reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)

    assert partition == ChannelPartition(live=(), library=(), legacy_count=0)


@pytest.mark.parametrize('argument', ['live_pool', 'library_channels', 'legacy_channels'])
def test_a_negative_count_is_refused(argument):
    """Each count is a number of channels."""
    counts = {'live_pool': 4, 'library_channels': 32, 'legacy_channels': 8} | {argument: -1}

    with pytest.raises(ValueError, match=argument):
        reserve_channels(**counts)


def test_the_channel_states_name_each_group():
    """The snapshot lists every channel with its group; idle until something plays.

    The mixer only grows (BUGS.md #145), so its default 8 channels stay and legacy keeps the
    three left over.
    """
    partition = start_reserved_mixer(live_pool=2, library_channels=3, legacy_channels=2)
    table = make_table(partition)

    snapshot = table.snapshot()

    assert [(state.index, state.group, state.state) for state in snapshot] == [
        (0, 'live', 'idle'),
        (1, 'live', 'idle'),
        (2, 'library', 'idle'),
        (3, 'library', 'idle'),
        (4, 'library', 'idle'),
        (5, 'legacy', 'idle'),
        (6, 'legacy', 'idle'),
        (7, 'legacy', 'idle'),
    ]


def test_the_snapshot_reads_live_and_legacy_channels_from_the_device():
    """The table does not own live or legacy channels: their state is the device's busy flag."""
    partition = start_reserved_mixer(live_pool=1, library_channels=1, legacy_channels=1)
    table = make_table(partition)
    noise = pygame.mixer.Sound(buffer=bytes(44100 * 4))
    pygame.mixer.Channel(0).play(noise)
    noise.play()

    states = {state.index: state.state for state in table.snapshot()}

    # 1 live + 1 library on the default 8 channels: 2-7 are legacy, and SDL put the play on 2
    assert states == {0: 'playing', 1: 'idle', 2: 'playing'} | dict.fromkeys(range(3, 8), 'idle')


def test_releasing_gives_the_reservation_back_for_a_restarted_mixer():
    """SDL keeps a reservation across a mixer restart; releasing first lets Sound.play() work."""
    start_mixer()
    reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)

    release_channels()
    pygame.mixer.quit()
    pygame.mixer.init()

    assert reserved_channel_count() == 0
    assert pygame.mixer.Sound(buffer=bytes(4 * 44100)).play() is not None


def test_releasing_without_a_mixer_does_nothing():
    """Without a mixer there is nothing to give back."""
    stop_mixer()

    release_channels()

    assert reserved_channel_count() == 0


def raise_inside() -> None:
    """Fail inside the reservation.

    Raises:
        RuntimeError: Always.
    """
    message = 'inside'
    raise RuntimeError(message)


class TestEveryChannelReserved:
    """every_channel_reserved: Sound.play() finds no channel inside, the reservation put back."""

    def test_inside_no_play_starts_and_afterwards_the_partition_is_back(self):
        """A partitioned mixer: None inside, then the legacy channels 36-43 again."""
        start_reserved_mixer()
        legacy_sound = pygame.mixer.Sound(buffer=bytes(44100 * 4))

        with every_channel_reserved():
            played_inside = legacy_sound.play()
            explicit_channel = pygame.mixer.Channel(40)
            explicit_channel.play(legacy_sound)
            explicit_busy = explicit_channel.get_busy()
        explicit_channel.stop()

        assert played_inside is None
        assert explicit_busy
        assert reserved_channel_count() == 36
        assert unreserved_channel_ids() == list(range(36, 44))

    def test_an_unpartitioned_mixer_is_left_unreserved(self):
        """No partition: nothing reserved before, nothing after; None inside."""
        start_mixer(channels=2)
        release_channels()
        legacy_sound = pygame.mixer.Sound(buffer=bytes(44100 * 4))

        with every_channel_reserved():
            played_inside = legacy_sound.play()

        assert played_inside is None
        assert reserved_channel_count() == 0
        assert unreserved_channel_ids() == list(range(8))

    def test_the_reservation_is_put_back_after_an_exception(self):
        """An exception inside propagates; the reservation is the partition's again."""
        start_reserved_mixer()

        with pytest.raises(RuntimeError, match='inside'), every_channel_reserved():
            raise_inside()

        assert reserved_channel_count() == 36
        assert unreserved_channel_ids() == list(range(36, 44))

    def test_a_mixer_grown_inside_keeps_the_reservation_from_before(self):
        """A partition inside grows the mixer: the reservation from before, on the grown mixer."""
        start_reserved_mixer()

        with every_channel_reserved():
            reserve_channels(live_pool=4, library_channels=40, legacy_channels=8)

        assert pygame.mixer.get_num_channels() == 52
        assert reserved_channel_count() == 36
        assert unreserved_channel_ids() == list(range(36, 52))

    def test_a_partition_made_inside_an_unpartitioned_mixer_is_undone(self):
        """No partition before: none remembered after, and nothing reserved."""
        start_mixer(channels=2)
        release_channels()

        with every_channel_reserved():
            reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)

        assert reserved_channel_count() == 0
        assert unreserved_channel_ids() == list(range(44))

    def test_without_a_mixer_it_does_nothing(self):
        """No mixer before: the body runs, and nothing is reserved or put back."""
        stop_mixer()

        with every_channel_reserved():
            mixer_inside = pygame.mixer.get_init()

        assert mixer_inside is None
        assert pygame.mixer.get_init() is None

    def test_a_mixer_stopped_inside_is_left_stopped(self):
        """The mixer quit inside: nothing to put back on, and no error."""
        start_reserved_mixer()

        with every_channel_reserved():
            stop_mixer()

        assert pygame.mixer.get_init() is None
        assert reserved_channel_count() == 0

    def test_a_nested_reservation_leaves_the_outer_one_in_place(self):
        """Nested (one silent game inside another's call): only the outermost puts back."""
        start_reserved_mixer()
        legacy_sound = pygame.mixer.Sound(buffer=bytes(44100 * 4))

        with every_channel_reserved():
            with every_channel_reserved():
                played_in_the_nested_one = legacy_sound.play()
            played_after_the_nested_one = legacy_sound.play()

        assert played_in_the_nested_one is None
        assert played_after_the_nested_one is None
        assert reserved_channel_count() == 36
        assert unreserved_channel_ids() == list(range(36, 44))

    def test_a_declaration_inside_keeps_every_channel_reserved_and_is_kept_after(self):
        """Declared inside: still no channel for a plain play; reserved up to the legacy after."""
        start_reserved_mixer()
        legacy_sound = pygame.mixer.Sound(buffer=bytes(44100 * 4))

        with every_channel_reserved():
            reserve_inner_game_channels(games=GAMES)
            played_inside = legacy_sound.play()

        assert played_inside is None
        assert reserved_channel_count() == 36
        assert unreserved_channel_ids() == list(range(108, 116))


# Two inner games: heard sets 36-67 and 68-99, live pools 100-103 and 104-107, legacy 108-115
GAMES = 2
HEARD_SET_A = tuple(range(36, 68))
HEARD_SET_B = tuple(range(68, 100))
FIRST_LIVE_POOL = (100, 101, 102, 103)
SECOND_LIVE_POOL = (104, 105, 106, 107)
LEGACY_ABOVE_THE_INNER_GAMES = list(range(108, 116))
# How long a sound plays: longer than any test's frames
LONG_SOUND_SECONDS = 2.0


@pytest.fixture
def channel_calls(mocker):
    """Record every call made on a mixer channel (the channels stay real).

    Returns:
        The list of (channel index, call, arguments).
    """
    RecordingChannel.calls.clear()
    mocker.patch('pygame.mixer.Channel', RecordingChannel)
    return RecordingChannel.calls


def declared_mixer(*, games: int = GAMES) -> ChannelPartition:
    """Partition a stereo mixer as an outer engine does, then declare its inner games' channels.

    Returns:
        The default partition.
    """
    partition = start_reserved_mixer()
    reserve_inner_game_channels(games=games)
    return partition


def partition_in(
    context: EngineContext, *, live_pool: int = 4, library_channels: int = 32
) -> ChannelPartition:
    """Take (or get) an inner context's partition, inside it.

    Returns:
        The partition.
    """
    with context.active():
        return inner_context_partition(live_pool=live_pool, library_channels=library_channels)


def make_heard(context: EngineContext) -> None:
    """Make an inner context heard: a heard set, then its route audible."""
    with context.active():
        take_heard_set()
        set_audible(audible=True)


def make_silent(context: EngineContext, *, table: VoiceTable | None = None) -> None:
    """Make an inner context silent: its table's voices fade on its set, which it gives back."""
    with context.active():
        if table is not None:
            table.fade_out_of_the_mixer(fade_seconds=0.05)
        set_audible(audible=False)
        give_back_heard_set()


def tile_table(context: EngineContext, partition: ChannelPartition) -> VoiceTable:
    """Make an inner context's voice table, inside it.

    Returns:
        The table.
    """
    with context.active():
        return make_table(partition, buses=unreserved_buses())


def play_long(table: VoiceTable, context: EngineContext | None = None) -> SoundHandle:
    """Play a long sound on a table (inside its context when given).

    Returns:
        The handle.
    """
    if context is None:
        return table.play(
            baked_sound(seconds=LONG_SOUND_SECONDS), owner=GAME_SCENE, **PLAY_DEFAULTS
        )
    with context.active():
        return table.play(
            baked_sound(seconds=LONG_SOUND_SECONDS), owner=GAME_SCENE, **PLAY_DEFAULTS
        )


def busy_channel_ids() -> list[int]:
    """Every mixer channel that is playing.

    Returns:
        Their indices.
    """
    return [
        index
        for index in range(pygame.mixer.get_num_channels())
        if pygame.mixer.Channel(index).get_busy()
    ]


class TestTheDeclaration:
    """reserve_inner_game_channels: the mixer grows once, at the host's startup (decision 4)."""

    def test_two_heard_sets_and_a_live_pool_per_game_lie_above_the_default_partition(self):
        """The default's channels stay; legacy above everything, as many as before."""
        default_partition = start_reserved_mixer()

        layout = reserve_inner_game_channels(games=GAMES)

        assert layout == InnerGameChannelLayout(
            heard_sets=(HEARD_SET_A, HEARD_SET_B),
            live_pools=(FIRST_LIVE_POOL, SECOND_LIVE_POOL),
            legacy_count=8,
        )
        assert pygame.mixer.get_num_channels() == 116
        assert reserved_channel_count() == 36
        assert default_partition.library == tuple(range(4, 36))
        assert unreserved_channel_ids() == LEGACY_ABOVE_THE_INNER_GAMES

    def test_the_mixer_never_grows_after_it(self, mocker):
        """Inner games built, heard, switched and finished: no set_num_channels at all."""
        declared_mixer()
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')
        first = EngineContext(name='first')
        second = EngineContext(name='second')

        tables = [tile_table(first, partition_in(first)), tile_table(second, partition_in(second))]
        for _round in range(3):
            make_heard(first)
            play_long(tables[0], first)
            make_silent(first, table=tables[0])
            make_heard(second)
            play_long(tables[1], second)
            make_silent(second, table=tables[1])
        for context in (first, second):
            with context.active():
                release_inner_context_channels()
        reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)
        third = EngineContext(name='third')
        partition_in(third)
        pygame.mixer.stop()

        set_num_channels.assert_not_called()

    def test_declaring_again_while_an_inner_game_holds_channels_is_refused(self):
        """A live pool held: refused, naming what to do first."""
        declared_mixer()
        partition_in(EngineContext(name='running'))

        with pytest.raises(ChannelsHeldError, match='finish them before'):
            reserve_inner_game_channels(games=GAMES + 1)

    def test_declaring_again_with_nothing_held_lays_out_afresh_and_only_grows(self):
        """More games: the mixer grows; fewer: it keeps its channels, the legacy count kept."""
        declared_mixer()
        finished = EngineContext(name='finished')
        partition_in(finished)
        with finished.active():
            release_inner_context_channels()

        more = reserve_inner_game_channels(games=GAMES + 1)
        channels_after_more = pygame.mixer.get_num_channels()
        fewer = reserve_inner_game_channels(games=1)

        assert more.live_pools[-1] == (108, 109, 110, 111)
        assert more.legacy_count == 8
        assert channels_after_more == 120
        assert fewer.live_pools == (FIRST_LIVE_POOL,)
        assert pygame.mixer.get_num_channels() == 120
        assert fewer.legacy_count == 16

    @pytest.mark.parametrize('games', [0, -1])
    def test_fewer_than_one_game_is_refused(self, games):
        """A declaration is for at least one inner game."""
        start_reserved_mixer()

        with pytest.raises(ValueError, match='games must be >= 1'):
            reserve_inner_game_channels(games=games)

    @pytest.mark.parametrize('argument', ['heard_set_channels', 'live_channels_per_game'])
    def test_a_negative_channel_count_is_refused(self, argument):
        """Each count is a number of channels."""
        start_reserved_mixer()

        with pytest.raises(ValueError, match=argument):
            reserve_inner_game_channels(games=1, **{argument: -1})

    def test_without_a_mixer_nothing_is_declared(self):
        """No mixer: an empty layout, and an inner game's partition is empty too."""
        stop_mixer()

        layout = reserve_inner_game_channels(games=GAMES)
        partition = partition_in(EngineContext(name='tile'))

        assert layout == InnerGameChannelLayout(heard_sets=(), live_pools=(), legacy_count=0)
        assert partition == ChannelPartition(live=(), library=(), legacy_count=0)

    def test_a_declaration_on_an_unpartitioned_mixer_without_an_engine_is_refused(self, mocker):
        """No partition and no engine to make one: refused, naming the ways; nothing changed.

        Declared from channel 0, the first partition made afterwards would cover the inner
        games' channels and forget them, and the first inner game built would fail.
        """
        start_mixer(channels=2)
        release_channels()
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

        with pytest.raises(
            InnerGameChannelsError,
            match=r'not partitioned yet.*GameEngine.*Scene\.INNER_GAMES.*default_channel_partition',
        ):
            reserve_inner_game_channels(games=1, heard_set_channels=2, live_channels_per_game=1)

        set_num_channels.assert_not_called()
        assert not inner_game_channels_declared()
        assert reserved_channel_count() == 0

    def test_a_declaration_from_an_inner_context_asks_no_engine_to_partition(self):
        """An inner engine never partitions: declared there, it lies above the outer partition."""
        start_reserved_mixer()
        inner = EngineContext(name='tile')

        with inner.active():
            set_render_target(surface=pygame.Surface((8, 8)))
            layout = reserve_inner_game_channels(games=GAMES)

        assert layout.heard_sets == (HEARD_SET_A, HEARD_SET_B)
        assert reserved_channel_count() == 36

    def test_a_partition_without_reserved_channels_still_counts_as_one(self):
        """--live-voice-pool 0 --sound-channels 0: partitioned, so the declaration starts at 0."""
        start_mixer(channels=2)
        reserve_channels(live_pool=0, library_channels=0, legacy_channels=8)

        layout = reserve_inner_game_channels(
            games=1, heard_set_channels=2, live_channels_per_game=1
        )

        assert layout.heard_sets == ((0, 1), (2, 3))
        assert layout.live_pools == ((4,),)
        assert unreserved_channel_ids() == list(range(5, 13))

    def test_plain_plays_never_land_on_the_inner_games_channels(self):
        """Every legacy channel busy: a ninth plain play finds none, never an inner channel."""
        declared_mixer()
        legacy_sound = pygame.mixer.Sound(buffer=bytes(44100 * 4))

        channels = [legacy_sound.play() for _ in range(8)]
        ninth = legacy_sound.play()

        assert sorted(channel.id for channel in channels) == LEGACY_ABOVE_THE_INNER_GAMES
        assert ninth is None

    def test_the_default_tables_snapshot_shows_the_legacy_channels_above_them(self):
        """Its legacy channels are the mixer's unreserved ones, 108-115."""
        table = make_table(declared_mixer())

        legacy = [state.index for state in table.snapshot() if state.group == 'legacy']

        assert legacy == LEGACY_ABOVE_THE_INNER_GAMES

    def test_a_growth_while_a_channel_plays_is_refused(self, mocker):
        """BUGS.md #145: a sound playing, the mixer too small: refused; nothing grown, declared."""
        start_reserved_mixer()
        playing = pygame.mixer.Sound(buffer=bytes(44100 * 4 * 4)).play()
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

        with pytest.raises(InnerGameChannelsError, match=r'BUGS\.md #145.*Scene\.INNER_GAMES'):
            reserve_inner_game_channels(games=GAMES)

        assert playing is not None
        assert playing.get_busy()
        set_num_channels.assert_not_called()
        assert pygame.mixer.get_num_channels() == 44
        assert not inner_game_channels_declared()
        pygame.mixer.stop()

    def test_declaring_again_while_a_channel_plays_needs_no_growth_and_is_allowed(self):
        """The mixer already holds them (an earlier declaration): nothing grows, so it may play."""
        declared_mixer()
        playing = pygame.mixer.Sound(buffer=bytes(44100 * 4 * 4)).play()

        layout = reserve_inner_game_channels(games=GAMES)

        assert playing is not None
        assert playing.get_busy()
        assert layout.live_pools == (FIRST_LIVE_POOL, SECOND_LIVE_POOL)
        pygame.mixer.stop()

    def test_an_engines_partition_declares_its_inner_games_in_the_same_one_growth(self, mocker):
        """reserve_channels(inner_games=2) on a fresh mixer: one set_num_channels, the layout."""
        start_mixer(channels=2)
        release_channels()
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

        partition = reserve_channels(
            live_pool=4, library_channels=32, legacy_channels=8, inner_games=GAMES
        )
        inner = partition_in(EngineContext(name='tile'))

        set_num_channels.assert_called_once_with(116)
        assert partition == ChannelPartition(
            live=(0, 1, 2, 3), library=tuple(range(4, 36)), legacy_count=8
        )
        assert inner.live == FIRST_LIVE_POOL
        assert unreserved_channel_ids() == LEGACY_ABOVE_THE_INNER_GAMES

    def test_an_engines_declaration_while_an_inner_game_holds_channels_is_refused(self):
        """A second host engine while the first one's inner games run: refused."""
        declared_mixer()
        partition_in(EngineContext(name='running'))

        with pytest.raises(ChannelsHeldError, match='before an engine declares its own'):
            reserve_channels(live_pool=4, library_channels=32, legacy_channels=8, inner_games=1)

    def test_a_negative_inner_game_count_is_refused(self):
        """inner_games is a count."""
        start_reserved_mixer()

        with pytest.raises(ValueError, match='inner_games'):
            reserve_channels(live_pool=4, library_channels=32, legacy_channels=8, inner_games=-1)

    def test_releasing_the_channels_forgets_the_declaration(self):
        """Shutdown's release: an inner game built afterwards fails (nothing declared)."""
        declared_mixer()
        stale = EngineContext(name='stale')
        partition_in(stale)

        release_channels()
        with stale.active():
            release_inner_context_channels()

        with pytest.raises(InnerGameChannelsError, match='reserve_inner_game_channels'):
            partition_in(EngineContext(name='after'))


class TestADefaultPartitionAfterTheDeclaration:
    """A new outer engine's partition while inner games' channels are declared."""

    def test_the_same_sizes_keep_the_inner_games_channels(self, mocker):
        """Same channels, no growth, the inner games' channels still reserved."""
        declared_mixer()
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

        partition = reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)

        assert partition == ChannelPartition(
            live=(0, 1, 2, 3), library=tuple(range(4, 36)), legacy_count=8
        )
        set_num_channels.assert_not_called()
        assert unreserved_channel_ids() == LEGACY_ABOVE_THE_INNER_GAMES

    def test_a_larger_one_while_an_inner_game_holds_channels_is_refused(self):
        """It would take the inner games' channels: refused, naming what a host does."""
        declared_mixer()
        partition_in(EngineContext(name='running'))

        with pytest.raises(ChannelsHeldError, match=r'channels 0-39.*finish them first'):
            reserve_channels(live_pool=4, library_channels=36, legacy_channels=8)

    def test_a_larger_one_with_nothing_held_forgets_the_declaration(self, caplog):
        """The host declares again above it: until then an inner game fails; never silently."""
        declared_mixer()

        with caplog.at_level(logging.WARNING, logger='game.audio.voices'):
            partition = reserve_channels(live_pool=4, library_channels=40, legacy_channels=8)

        assert partition.library == tuple(range(4, 44))
        assert "covers the inner games' channels declared from channel 36" in caplog.text
        with pytest.raises(InnerGameChannelsError, match='no channels are declared'):
            partition_in(EngineContext(name='tile'))


class TestAGrowthWhileAChannelPlays:
    """BUGS.md #145: no partition grows the mixer while a channel plays (MixerBusyError)."""

    def test_a_partition_that_must_grow_is_refused_and_changes_nothing(self, mocker):
        """A sound playing on a mixer too small: refused; nothing grown, nothing reserved."""
        start_mixer(channels=2)
        release_channels()
        playing = long_plain_sound().play()
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

        with pytest.raises(MixerBusyError, match=r'grow the mixer to 44 channels.*BUGS\.md #145'):
            reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)

        assert playing is not None
        assert playing.get_busy()
        set_num_channels.assert_not_called()
        assert pygame.mixer.get_num_channels() == 8
        assert reserved_channel_count() == 0
        pygame.mixer.stop()

    def test_a_refused_partition_keeps_the_declaration_it_would_have_covered(self):
        """Refused before the declaration is forgotten: inner games still build."""
        declared_mixer()
        playing = long_plain_sound().play()

        with pytest.raises(MixerBusyError):
            reserve_channels(live_pool=4, library_channels=200, legacy_channels=8)
        inner = partition_in(EngineContext(name='tile'))

        assert playing is not None
        assert inner_game_channels_declared()
        assert inner.live == FIRST_LIVE_POOL
        pygame.mixer.stop()

    def test_a_partition_that_needs_no_growth_is_made_while_a_channel_plays(self, mocker):
        """A second engine's partition of the same sizes: nothing grows, so a sound may play."""
        start_reserved_mixer()
        playing = long_plain_sound().play()
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

        partition = reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)

        assert playing is not None
        assert playing.get_busy()
        assert partition.library == tuple(range(4, 36))
        set_num_channels.assert_not_called()
        pygame.mixer.stop()


class TestInnerPartitions:
    """An inner context's partition: its own slots, a live pool from the declaration."""

    def test_an_inner_partition_has_logical_slots_and_the_first_free_live_pool(self):
        """Its recording's slots (0-31) and live pool 100-103; the next game 104-107."""
        declared_mixer()
        first_context = EngineContext(name='first')

        first = partition_in(first_context)
        second = partition_in(EngineContext(name='second'), live_pool=2, library_channels=6)
        again = partition_in(first_context, live_pool=1, library_channels=1)

        assert first == ChannelPartition(
            live=FIRST_LIVE_POOL,
            library=tuple(range(32)),
            legacy_count=8,
            plays_on_a_heard_set=True,
        )
        assert second.live == SECOND_LIVE_POOL[:2]
        assert second.library == tuple(range(6))
        assert again == first

    def test_an_inner_game_past_the_declared_count_is_refused(self):
        """Two declared, a third: refused, naming the call."""
        declared_mixer()
        partition_in(EngineContext(name='first'))
        partition_in(EngineContext(name='second'))

        with pytest.raises(
            InnerGameChannelsError,
            match=r"all 2 inner games declared are running \('first', 'second'\): finish one "
            r'\(InnerGame\.finish\(\), also for one the host dropped\)',
        ):
            partition_in(EngineContext(name='third'))

    def test_an_inner_game_with_nothing_declared_is_refused(self):
        """No declaration: refused, naming the call to make."""
        start_reserved_mixer()

        with pytest.raises(InnerGameChannelsError, match='reserve_inner_game_channels'):
            partition_in(EngineContext(name='tile'))

    def test_a_live_pool_larger_than_declared_is_refused(self):
        """--live-voice-pool 5 of 4 declared: refused (a capped pool would change the game)."""
        declared_mixer()

        with pytest.raises(InnerGameChannelsError, match='--live-voice-pool 5'):
            partition_in(EngineContext(name='tile'), live_pool=5)

    def test_a_negative_size_is_refused(self):
        """Each size is a number of channels."""
        declared_mixer()

        with pytest.raises(ValueError, match='library_channels'):
            partition_in(EngineContext(name='tile'), library_channels=-1)

    def test_a_finished_games_live_pool_is_stopped_and_reused(self):
        """Its channels go quiet, and the next inner game takes the same pool."""
        declared_mixer()
        finished = EngineContext(name='finished')
        pool = partition_in(finished).live
        pygame.mixer.Channel(pool[0]).play(pygame.mixer.Sound(buffer=bytes(44100 * 4)))

        with finished.active():
            release_inner_context_channels()
        busy_after = pygame.mixer.Channel(pool[0]).get_busy()
        reused = partition_in(EngineContext(name='next'))

        assert busy_after is False
        assert finished.value(slot=INNER_CHANNELS_SLOT).partition is None
        assert reused.live == pool

    def test_releasing_a_context_holding_nothing_does_nothing(self):
        """No partition taken: nothing to give back."""
        declared_mixer()

        with EngineContext(name='tile').active():
            release_inner_context_channels()

        assert unreserved_channel_ids() == LEGACY_ABOVE_THE_INNER_GAMES

    def test_a_restarted_mixer_has_no_declaration(self):
        """A restart forgets it: an inner game then fails, and an old one frees nothing."""
        declared_mixer()
        before = EngineContext(name='before')
        partition_in(before)
        start_reserved_mixer()

        with before.active():
            release_inner_context_channels()
        with pytest.raises(InnerGameChannelsError, match='no channels are declared'):
            partition_in(EngineContext(name='after'))

    def test_an_inner_contexts_default_partition_is_its_inner_partition(self):
        """A scene manager without a game engine, inside an inner context, never partitions."""
        declared_mixer()
        context = EngineContext(name='tile')

        with context.active():
            set_render_target(surface=pygame.Surface((8, 8)))
            partition = default_channel_partition()

        assert partition.live == FIRST_LIVE_POOL
        assert partition.plays_on_a_heard_set
        assert context.value(slot=INNER_CHANNELS_SLOT).partition == partition
        assert reserved_channel_count() == 36

    def test_a_silent_tiles_live_voice_leaves_a_plain_sound_on_the_top_legacy_channel(self):
        """The reviewer's case: the plain sound on the top channel plays on (no growth, no move)."""
        declared_mixer()
        plain_sound = pygame.mixer.Sound(buffer=bytes(44100 * 4 * 4))
        plain_channels = [plain_sound.play() for _ in range(8)]
        top_channel = pygame.mixer.Channel(LEGACY_ABOVE_THE_INNER_GAMES[-1])
        for channel in plain_channels:
            assert channel is not None
            if channel.id != top_channel.id:
                channel.stop()
        context = EngineContext(name='small tile')

        with context.active():
            set_audible(audible=False)
            partition = inner_context_partition(live_pool=2, library_channels=6)
            voice = LiveAudio(channel_indices=partition.live).create_instrument_voice(
                owner=GAME_SCENE, instrument=Instrument(wave='sine', live=True), frequency=220.0
            )
            voice.stream.start()

        assert top_channel.get_busy()
        assert top_channel.get_sound() is plain_sound
        assert busy_channel_ids() == [partition.live[0], top_channel.id]
        voice.stream.stop_now()
        pygame.mixer.stop()


class TestHeardSets:
    """Only the heard inner game plays library channels: on one of two heard sets."""

    def test_the_heard_tile_and_the_default_context_play_to_their_ends_on_their_own_channels(
        self,
    ):
        """The collision Task 2 found: both voices to their end, distinct channels, no steal."""
        default_partition = declared_mixer()
        default_table = make_table(default_partition, buses=unreserved_buses())
        context = EngineContext(name='tile')
        table = tile_table(context, partition_in(context))
        make_heard(context)
        tile_handle = play_long(table, context)
        default_handle = play_long(default_table)
        tile_channel = pygame.mixer.Channel(HEARD_SET_A[tile_handle.slot])
        default_channel = pygame.mixer.Channel(default_partition.library[default_handle.slot])
        tile_sound = tile_channel.get_sound()
        default_sound = default_channel.get_sound()
        seen = []
        frames = round(LONG_SOUND_SECONDS * 60)
        for _ in range(frames - 1):
            seen.extend((
                (tile_handle.is_playing, default_handle.is_playing),
                (tile_channel.get_sound(), default_channel.get_sound()),
            ))
            with context.active():
                advance_frames(table, count=1)
            default_table.advance(dt=FRAME_SECONDS, paused_owners=frozenset())
        with context.active():
            advance_frames(table, count=1)
        default_table.advance(dt=FRAME_SECONDS, paused_owners=frozenset())
        ended = (tile_handle.is_playing, default_handle.is_playing)
        pygame.mixer.stop()

        assert tile_sound is not None
        assert default_sound is not None
        assert seen == [(True, True), (tile_sound, default_sound)] * (frames - 1)
        assert ended == (False, False)
        assert table.counters.steals == default_table.counters.steals == 0

    def test_a_switch_fades_the_old_tile_on_its_set_while_the_new_one_plays_on_the_other(
        self, channel_calls
    ):
        """A then B; the next switch takes A again (stopping what still sounds there)."""
        declared_mixer()
        first = EngineContext(name='first')
        second = EngineContext(name='second')
        first_table = tile_table(first, partition_in(first))
        second_table = tile_table(second, partition_in(second))

        make_heard(first)
        first_handle = play_long(first_table, first)
        first_channel = pygame.mixer.Channel(HEARD_SET_A[first_handle.slot])
        make_silent(first, table=first_table)
        make_heard(second)
        second_handle = play_long(second_table, second)
        second_channel = pygame.mixer.Channel(HEARD_SET_B[second_handle.slot])
        both_sounding = (first_channel.get_busy(), second_channel.get_busy())
        calls_of_the_first_switch = list(channel_calls)
        # Set A still sounding when it is taken again (a fade not yet run out, on any machine)
        first_channel.play(pygame.mixer.Sound(buffer=bytes(44100 * 4 * 4)))
        channel_calls.clear()
        make_silent(second, table=second_table)
        make_heard(first)
        again_handle = play_long(first_table, first)
        calls_of_the_second_switch = list(channel_calls)
        pygame.mixer.stop()

        assert (first_channel.id, 'fadeout', (50,)) in calls_of_the_first_switch
        assert (second_channel.id, 'play') in [
            (index, kind) for index, kind, _ in calls_of_the_first_switch
        ]
        assert both_sounding == (True, True)
        assert first_handle.is_playing
        # The first tile's voice from before is never heard again; its new one plays on set A
        assert (second_channel.id, 'fadeout', (50,)) in calls_of_the_second_switch
        assert (first_channel.id, 'stop', ()) in calls_of_the_second_switch
        assert HEARD_SET_A[again_handle.slot] in [
            index for index, kind, _ in calls_of_the_second_switch if kind == 'play'
        ]

    def test_a_third_heard_tile_is_refused_while_two_are_heard(self):
        """Both sets held: a third take is refused; giving one back lets it in."""
        declared_mixer(games=3)
        contexts = [EngineContext(name=name) for name in ('first', 'second', 'third')]
        for context in contexts:
            partition_in(context)
        make_heard(contexts[0])
        make_heard(contexts[1])

        with pytest.raises(InnerGameChannelsError, match='two inner games are heard'):
            make_heard(contexts[2])
        make_silent(contexts[0])
        make_heard(contexts[2])

        with contexts[2].active():
            assert heard_set_start() == HEARD_SET_A[0]

    def test_taking_a_set_twice_keeps_the_one_held(self):
        """Already heard: the same set."""
        declared_mixer()
        context = EngineContext(name='tile')
        partition_in(context)
        make_heard(context)

        with context.active():
            take_heard_set()
            start = heard_set_start()

        assert start == HEARD_SET_A[0]

    def test_a_tile_too_big_for_a_heard_set_replays_silent_and_cannot_be_heard(self):
        """--sound-channels 33: its partition is made; taking a heard set is refused."""
        declared_mixer()
        context = EngineContext(name='big tile')
        partition = partition_in(context, library_channels=33)

        with pytest.raises(InnerGameChannelsError, match='--sound-channels 33'):
            make_heard(context)

        assert len(partition.library) == 33
        with context.active():
            assert heard_set_start() is None

    def test_a_context_without_a_partition_cannot_be_heard(self):
        """Never built (or finished): refused."""
        declared_mixer()

        with pytest.raises(InnerGameChannelsError, match='holds no channels'):
            make_heard(EngineContext(name='tile'))

    def test_giving_back_without_a_set_does_nothing(self):
        """Silent already: nothing to give back."""
        declared_mixer()
        context = EngineContext(name='tile')
        partition_in(context)

        make_silent(context)

        with context.active():
            assert heard_set_start() is None

    def test_an_audible_inner_table_without_a_set_touches_no_channel(self, channel_calls):
        """Its route audible but no heard set taken: it stays off the mixer."""
        declared_mixer()
        context = EngineContext(name='tile')
        table = tile_table(context, partition_in(context))
        with context.active():
            set_audible(audible=True)

        handle = play_long(table, context)

        assert channel_calls == []
        assert handle.is_playing
        library = [state.index for state in table.snapshot() if state.group == 'library']
        assert library == list(range(32))

    def test_a_heard_tiles_steal_flashes_its_heard_set_channel(self):
        """The debug panel's steal flash names the mixer channel the snapshot shows."""
        declared_mixer()
        context = EngineContext(name='tile')
        table = tile_table(context, partition_in(context, live_pool=0, library_channels=1))
        make_heard(context)
        play_long(table, context)
        with context.active():
            table.play(
                baked_sound(seconds=LONG_SOUND_SECONDS),
                owner=GAME_SCENE,
                **(PLAY_DEFAULTS | {'priority': 60}),
            )
        stolen = table.recently_stolen_channels()
        shown = [state.index for state in table.snapshot() if state.group == 'library']
        pygame.mixer.stop()

        assert stolen == frozenset({HEARD_SET_A[0]})
        assert shown == [HEARD_SET_A[0]]

    def test_a_silenced_heard_channel_is_marked_and_the_snapshot_shows_the_set(self):
        """FrameSilencer's channel numbers are mixer channels: the heard set's."""
        declared_mixer()
        context = EngineContext(name='tile')
        table = tile_table(context, partition_in(context, live_pool=0))
        make_heard(context)
        handle = play_long(table, context)

        table.silenced(HEARD_SET_A[handle.slot])
        snapshot = table.snapshot()
        pygame.mixer.stop()

        assert snapshot[handle.slot].index == HEARD_SET_A[handle.slot]
        assert snapshot[handle.slot].state == 'idle'

    def test_a_tiles_answers_are_the_same_heard_silent_and_alone(self):
        """Steals, drops, ends and is_playing frame by frame: its slots are its recording's."""
        alone_answers = _three_slot_answers(
            table=make_table(
                start_reserved_mixer(live_pool=0, library_channels=3, legacy_channels=8),
                buses=unreserved_buses(),
            )
        )
        declared_mixer()
        silent = EngineContext(name='silent')
        silent_answers = _three_slot_answers(
            table=tile_table(silent, partition_in(silent, library_channels=3)), context=silent
        )
        heard = EngineContext(name='heard')
        heard_table = tile_table(heard, partition_in(heard, library_channels=3))
        make_heard(heard)
        heard_answers = _three_slot_answers(table=heard_table, context=heard)
        pygame.mixer.stop()

        assert silent_answers == alone_answers
        assert heard_answers == alone_answers
        assert alone_answers[-1][1] == VoiceCounters(steals=2, delayed_plays=2, dropped_plays=1)


def _three_slot_answers(
    *, table: VoiceTable, context: EngineContext | None = None
) -> list[tuple[object, ...]]:
    """Play six sounds into a three-slot table, with steals, a drop and ends, frame by frame.

    Returns:
        Per frame: each handle's is_playing, the counters and the voice count.
    """
    with contextlib.ExitStack() as stack:
        if context is not None:
            stack.enter_context(context.active())
        handles = [
            table.play(baked_sound(seconds=0.1 * (index + 1)), owner=GAME_SCENE, **PLAY_DEFAULTS)
            for index in range(3)
        ]
        answers: list[tuple[object, ...]] = []
        for frame in range(30):
            if frame == 2:
                handles.extend(
                    table.play(
                        baked_sound(seconds=0.2),
                        owner=GAME_SCENE,
                        **(PLAY_DEFAULTS | {'priority': priority}),
                    )
                    for priority in (60, 60, 10)
                )
            table.advance(dt=FRAME_SECONDS, paused_owners=frozenset())
            answers.append((
                tuple(handle.is_playing for handle in handles),
                table.counters,
                table.voice_count,
            ))
    return answers


def long_plain_sound() -> pygame.mixer.Sound:
    """A plain sound longer than any test (four seconds of stereo 16-bit silence).

    Returns:
        The sound.
    """
    return pygame.mixer.Sound(buffer=bytes(44100 * 4 * 4))


class AdvancingChannel(pygame.mixer.Channel):
    """A real channel whose playing chunk ends right after the first read of it (a race).

    The mixer thread may end a chunk between two reads; here it happens at once after the
    first ``get_sound`` or ``get_queue``: ``Channel.stop`` starts the queued chunk (pygame-ce
    2.5.8), as the chunk's end would.
    """

    advancing_channel_ids: ClassVar[set[int]] = set()

    def get_sound(self):
        """Read the playing chunk, then let it end.

        Returns:
            The chunk playing when read.
        """
        sound = super().get_sound()
        self._advance_once()
        return sound

    def get_queue(self):
        """Read the queued chunk, then let the playing one end.

        Returns:
            The chunk queued when read.
        """
        queued = super().get_queue()
        self._advance_once()
        return queued

    def _advance_once(self):
        """End the playing chunk the first time, on a channel that advances."""
        if self.id in AdvancingChannel.advancing_channel_ids:
            AdvancingChannel.advancing_channel_ids.discard(self.id)
            super().stop()


def play_plain_followed(context: EngineContext, sound: pygame.mixer.Sound) -> pygame.mixer.Channel:
    """Play a plain sound inside an inner context, followed (an audible tile's step).

    Returns:
        The channel it took.
    """
    with context.active(), plain_plays_followed():
        channel = sound.play()
    assert channel is not None
    return channel


def plain_plays_of(context: EngineContext) -> tuple[int, ...]:
    """The channels playing a plain play the context started.

    Returns:
        Their indices.
    """
    with context.active():
        return plain_play_channel_indices()


class TestOnlyTheHeardTileIsHeard:
    """Decision 6: going silent stops a tile's plain plays and mutes its live pool, only its own."""

    def test_a_heard_tiles_plain_play_stops_when_it_goes_silent_and_the_default_one_plays_on(
        self,
    ):
        """The tile's sound stops at once; the default context's, playing beside it, plays on."""
        declared_mixer()
        default_sound = long_plain_sound()
        default_channel = default_sound.play()
        assert default_channel is not None
        context = EngineContext(name='tile')
        partition_in(context)
        make_heard(context)
        tile_sound = long_plain_sound()

        tile_channel = play_plain_followed(context, tile_sound)
        followed = plain_plays_of(context)
        make_silent(context)

        assert tile_channel.id in LEGACY_ABOVE_THE_INNER_GAMES
        assert followed == (tile_channel.id,)
        assert not tile_channel.get_busy()
        assert plain_plays_of(context) == ()
        assert default_channel.get_busy()
        assert default_channel.get_sound() is default_sound
        pygame.mixer.stop()

    def test_a_channel_its_followed_sound_left_is_never_stopped(self):
        """The tile's sound ended; the default context's sound now on that channel plays on."""
        declared_mixer()
        context = EngineContext(name='tile')
        partition_in(context)
        make_heard(context)
        tile_channel = play_plain_followed(context, long_plain_sound())
        tile_channel.stop()
        default_sound = long_plain_sound()
        tile_channel.play(default_sound)

        followed = plain_plays_of(context)
        make_silent(context)

        assert followed == ()
        assert tile_channel.get_busy()
        assert tile_channel.get_sound() is default_sound
        pygame.mixer.stop()

    def test_a_sound_already_playing_when_the_call_began_is_not_the_tiles(self):
        """Only a channel playing another sound after the call than before it is the tile's."""
        declared_mixer()
        default_channel = long_plain_sound().play()
        assert default_channel is not None
        context = EngineContext(name='tile')
        partition_in(context)

        with context.active(), plain_plays_followed():
            during = plain_play_channel_indices()

        assert during == ()
        assert plain_plays_of(context) == ()
        pygame.mixer.stop()

    def test_going_silent_inside_a_followed_call_stops_what_the_call_started(self):
        """A finish going silent: the play started in the same call is stopped, nothing kept."""
        declared_mixer()
        context = EngineContext(name='tile')
        partition_in(context)
        make_heard(context)

        with context.active(), plain_plays_followed():
            channel = long_plain_sound().play()
            assert channel is not None
            started = plain_play_channel_indices()
            set_audible(audible=False)
            give_back_heard_set()

        assert started == (channel.id,)
        assert not channel.get_busy()
        assert plain_plays_of(context) == ()

    def test_a_plain_play_started_after_going_silent_in_the_call_is_stopped_as_it_ends(self):
        """Silent mid-call (a finish), then a plain play: stopped at the call's end, not kept.

        The default context's sound playing beside it plays on.
        """
        declared_mixer()
        default_sound = long_plain_sound()
        default_channel = default_sound.play()
        assert default_channel is not None
        context = EngineContext(name='tile')
        partition_in(context)
        make_heard(context)

        with context.active(), plain_plays_followed():
            set_audible(audible=False)
            give_back_heard_set()
            late_channel = long_plain_sound().play()
            assert late_channel is not None
            busy_inside_the_call = late_channel.get_busy()

        assert busy_inside_the_call
        assert not late_channel.get_busy()
        assert plain_plays_of(context) == ()
        assert default_channel.get_sound() is default_sound
        pygame.mixer.stop()

    def test_a_chunk_moving_from_the_queue_between_the_reads_is_muted(self, mocker):
        """The playing chunk ends right after the first read: the one that took over is muted.

        Read the playing chunk first, the queued one would have moved to playing before the
        queue was read, and be missed at volume 1.
        """
        declared_mixer()
        context = EngineContext(name='tile')
        partition = partition_in(context)
        make_heard(context)
        live_channel = pygame.mixer.Channel(partition.live[0])
        playing_chunk = long_plain_sound()
        queued_chunk = long_plain_sound()
        live_channel.play(playing_chunk)
        live_channel.queue(queued_chunk)
        AdvancingChannel.advancing_channel_ids = {partition.live[0]}
        mocker.patch('pygame.mixer.Channel', AdvancingChannel)

        make_silent(context)

        assert AdvancingChannel.advancing_channel_ids == set()
        assert pygame.mixer.Channel(partition.live[0]).get_sound() is queued_chunk
        assert queued_chunk.get_volume() == 0.0
        pygame.mixer.stop()

    def test_going_silent_mutes_the_chunks_on_its_live_pool(self):
        """The chunk playing and the one queued are at volume 0 at once; the channel plays on."""
        declared_mixer()
        context = EngineContext(name='tile')
        partition = partition_in(context)
        make_heard(context)
        live_channel = pygame.mixer.Channel(partition.live[0])
        playing_chunk = long_plain_sound()
        queued_chunk = long_plain_sound()
        live_channel.play(playing_chunk)
        live_channel.queue(queued_chunk)

        make_silent(context)

        assert live_channel.get_busy()
        assert playing_chunk.get_volume() == 0.0
        assert queued_chunk.get_volume() == 0.0
        pygame.mixer.stop()

    def test_a_restarted_mixer_forgets_the_followed_plays(self):
        """A followed channel the restarted mixer no longer has is not asked about."""
        declared_mixer()
        context = EngineContext(name='tile')
        partition = partition_in(context)
        make_heard(context)
        play_plain_followed(context, long_plain_sound())

        stop_mixer()
        start_mixer()
        followed_after_the_restart = plain_plays_of(context)
        stop_mixer()
        followed_without_a_mixer = plain_plays_of(context)
        with context.active():
            set_audible(audible=False)
        start_mixer()

        assert partition.live == FIRST_LIVE_POOL
        assert followed_after_the_restart == ()
        assert followed_without_a_mixer == ()
        assert unreserved_channel_indices() == range(8)

    def test_without_a_mixer_there_is_no_unreserved_channel(self):
        """Nothing to follow, nothing to read."""
        stop_mixer()

        assert unreserved_channel_indices() == range(0)

    def test_an_inner_contexts_channels_are_its_heard_set_live_pool_and_plain_plays(self):
        """Never the default context's, nor another tile's."""
        declared_mixer()
        long_plain_sound().play()
        context = EngineContext(name='tile')
        other = EngineContext(name='other')
        partition_in(context)
        partition_in(other)
        with context.active():
            silent_channels = current_inner_context_channel_indices()
        make_heard(context)
        tile_channel = play_plain_followed(context, long_plain_sound())

        with context.active():
            heard_channels = current_inner_context_channel_indices()
        with EngineContext(name='never built').active():
            channels_of_a_context_without_any = current_inner_context_channel_indices()
        make_silent(context)

        assert silent_channels == FIRST_LIVE_POOL
        assert heard_channels == (*HEARD_SET_A, *FIRST_LIVE_POOL, tile_channel.id)
        assert channels_of_a_context_without_any == ()
        pygame.mixer.stop()


def inner_tile(*, heard: bool) -> tuple[EngineContext, ChannelPartition]:
    """An inner context (it has a render target) holding its channels, heard or silent.

    Returns:
        The context and its partition.
    """
    context = EngineContext(name='tile')
    with context.active():
        set_render_target(surface=pygame.Surface((8, 8)))
    partition = partition_in(context)
    if heard:
        make_heard(context)
    return context, partition


class TestASilencerInAnInnerContext:
    """FrameSilencer in an inner context stops only that context's channels (the guard)."""

    def test_a_rebuilds_silence_stops_the_tiles_channels_and_no_other(self):
        """Its heard set, live pool and plain play stop; the default's and another tile's go on."""
        declared_mixer()
        default_sound = long_plain_sound()
        default_channel = default_sound.play()
        assert default_channel is not None
        _other, other_partition = inner_tile(heard=False)
        other_live_channel = pygame.mixer.Channel(other_partition.live[0])
        other_live_channel.play(long_plain_sound())
        context, partition = inner_tile(heard=True)
        heard_channel = pygame.mixer.Channel(HEARD_SET_A[0])
        heard_channel.play(long_plain_sound())
        live_channel = pygame.mixer.Channel(partition.live[0])
        live_channel.play(long_plain_sound())
        silencer = FrameSilencer()

        with context.active(), plain_plays_followed():
            plain_channel = long_plain_sound().play()
            assert plain_channel is not None
            silencer.begin()
            silencer.silence_frame()
            silencer.finish()

        assert not heard_channel.get_busy()
        assert not live_channel.get_busy()
        assert not plain_channel.get_busy()
        assert default_channel.get_sound() is default_sound
        assert other_live_channel.get_busy()
        make_silent(context)
        pygame.mixer.stop()

    def test_a_fast_forwards_silence_spares_the_tiles_playing_sounds_and_never_stops_others(
        self,
    ):
        """What the tile played at begin plays on; its new sound stops; the default's plays on."""
        declared_mixer()
        context, partition = inner_tile(heard=True)
        spared_sound = long_plain_sound()
        spared_channel = play_plain_followed(context, spared_sound)
        silencer = FrameSilencer(spares_playing_sounds=True)
        live_channel = pygame.mixer.Channel(partition.live[0])
        idle_channel = pygame.mixer.Channel(partition.live[1])

        with context.active():
            silencer.begin()
            live_channel.play(long_plain_sound())
            default_sound = long_plain_sound()
            default_channel = pygame.mixer.Channel(LEGACY_ABOVE_THE_INNER_GAMES[-1])
            default_channel.play(default_sound)
            silencer.silence_frame()
            silencer.finish()

        assert spared_channel.get_sound() is spared_sound
        assert not live_channel.get_busy()
        assert not idle_channel.get_busy()
        assert default_channel.get_sound() is default_sound
        make_silent(context)
        pygame.mixer.stop()
