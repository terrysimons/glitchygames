"""Tests for the live/library/legacy channel partition (impl spec 7.1, AUD-MIX-008)."""

import pygame
import pytest

from glitchygames.audio.engine import default_channel_partition
from glitchygames.audio.live import reserve_live_voice_pool
from glitchygames.audio.route import set_audible
from glitchygames.audio.voices import (
    CHANNEL_BLOCK_SLOT,
    ChannelPartition,
    ChannelsHeldError,
    context_channel_block,
    every_channel_reserved,
    free_context_channel_block,
    release_channels,
    reserve_channels,
    reserved_channel_count,
)
from glitchygames.engine_context import EngineContext
from glitchygames.render_target import set_render_target
from tests.audio.library_support import start_mixer, stop_mixer
from tests.audio.voice_support import (
    FRAME_SECONDS,
    GAME_SCENE,
    PLAY_DEFAULTS,
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


def test_the_live_pool_wrapper_after_a_partition_keeps_the_library_reserved(mocker):
    """reserve_live_voice_pool after reserve_channels neither grows nor lowers the reservation."""
    start_reserved_mixer()
    set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')
    legacy_sound = pygame.mixer.Sound(buffer=bytes(44100 * 4))

    live_channels = reserve_live_voice_pool(4)
    channels = [legacy_sound.play() for _ in range(8)]
    ninth = legacy_sound.play()

    assert live_channels == (0, 1, 2, 3)
    set_num_channels.assert_not_called()
    assert pygame.mixer.get_num_channels() == 44
    assert sorted(channel.id for channel in channels) == list(range(36, 44))
    assert ninth is None


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

    def test_a_block_taken_inside_keeps_every_channel_reserved_and_is_kept_after(self):
        """A silent inner build takes its block inside: still no channel for a plain play."""
        start_reserved_mixer()
        legacy_sound = pygame.mixer.Sound(buffer=bytes(44100 * 4))

        with every_channel_reserved():
            block = block_in(new_inner_context())
            played_inside = legacy_sound.play()

        assert played_inside is None
        assert block.library == tuple(range(36, 68))
        assert reserved_channel_count() == 36
        assert unreserved_channel_ids() == list(range(72, 80))


def new_inner_context(*, name: str = 'tile') -> EngineContext:
    """Make a context standing for an Arcade tile's (only its slots matter here).

    Returns:
        The context.
    """
    return EngineContext(name=name)


def block_in(
    context: EngineContext, *, live_pool: int = 4, library_channels: int = 32
) -> ChannelPartition:
    """Take (or get) a context's channel block, inside it.

    Returns:
        The block's partition.
    """
    with context.active():
        return context_channel_block(live_pool=live_pool, library_channels=library_channels)


def free_block_of(context: EngineContext) -> None:
    """Give a context's channel block back, inside it."""
    with context.active():
        free_context_channel_block()


class TestChannelBlocks:
    """A channel block per inner context (Arcade sub-plan 4, decisions 4 and 5)."""

    def test_a_block_lies_above_the_default_partition_which_keeps_its_channels(self):
        """Library 36-67, live 68-71; the default's 0-35 and its 8 legacy channels remain."""
        default_partition = start_reserved_mixer()

        block = block_in(new_inner_context())

        assert block == ChannelPartition(
            live=tuple(range(68, 72)), library=tuple(range(36, 68)), legacy_count=8
        )
        assert pygame.mixer.get_num_channels() == 80
        assert reserved_channel_count() == 36
        assert default_partition.library == tuple(range(4, 36))
        # The legacy channels move above every block, as many as before
        assert unreserved_channel_ids() == list(range(72, 80))

    def test_blocks_never_overlap_each_other_or_the_default_partition(self):
        """Two tiles: two disjoint blocks, both above the default's channels."""
        default_partition = start_reserved_mixer()

        first = block_in(new_inner_context(name='first'))
        second = block_in(new_inner_context(name='second'))

        default_channels = {*default_partition.live, *default_partition.library}
        first_channels = {*first.live, *first.library}
        second_channels = {*second.live, *second.library}
        assert len(first_channels) == len(second_channels) == 36
        assert not default_channels & first_channels
        assert not default_channels & second_channels
        assert not first_channels & second_channels
        assert unreserved_channel_ids() == list(range(108, 116))

    def test_an_inner_contexts_default_partition_is_its_block(self):
        """A scene manager without a game engine, inside an inner context, never partitions."""
        start_reserved_mixer()
        context = new_inner_context()

        with context.active():
            set_render_target(surface=pygame.Surface((8, 8)))
            partition = default_channel_partition()

        assert partition == ChannelPartition(
            live=tuple(range(68, 72)), library=tuple(range(36, 68)), legacy_count=8
        )
        assert context.value(slot=CHANNEL_BLOCK_SLOT).partition == partition
        assert reserved_channel_count() == 36

    def test_a_block_has_the_sizes_its_context_asked_for(self):
        """--sound-channels 6 and --live-voice-pool 2: six library and two live channels."""
        start_reserved_mixer()

        block = block_in(new_inner_context(), live_pool=2, library_channels=6)

        assert block == ChannelPartition(
            live=(42, 43), library=tuple(range(36, 42)), legacy_count=8
        )
        assert reserved_channel_count() == 36
        assert unreserved_channel_ids() == list(range(44, 52))

    def test_a_context_asking_again_gets_the_block_it_has(self, mocker):
        """One block per context, whatever it asks for later; nothing grows again."""
        start_reserved_mixer()
        context = new_inner_context()
        first = block_in(context)
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

        again = block_in(context, live_pool=1, library_channels=1)

        assert again == first
        set_num_channels.assert_not_called()

    def test_a_freed_block_is_reused_without_growing_or_lowering_the_reservation(self, mocker):
        """The next tile gets the freed channels; the mixer and its reservation stay."""
        start_reserved_mixer()
        finished = new_inner_context(name='finished')
        freed = block_in(finished)
        free_block_of(finished)
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

        reused = block_in(new_inner_context(name='next'))

        assert reused == freed
        assert finished.value(slot=CHANNEL_BLOCK_SLOT).partition is None
        set_num_channels.assert_not_called()
        assert unreserved_channel_ids() == list(range(72, 80))

    def test_a_smaller_block_fits_in_a_freed_gap_and_a_larger_one_goes_on_top(self):
        """First fit: a gap between held blocks is used when large enough."""
        start_reserved_mixer()
        first = new_inner_context(name='first')
        block_in(first, live_pool=1, library_channels=3)
        block_in(new_inner_context(name='second'), live_pool=1, library_channels=3)
        free_block_of(first)

        small = block_in(new_inner_context(name='small'), live_pool=1, library_channels=1)
        large = block_in(new_inner_context(name='large'), live_pool=1, library_channels=4)
        what_is_left = block_in(new_inner_context(name='left'), live_pool=0, library_channels=2)

        assert small == ChannelPartition(live=(37,), library=(36,), legacy_count=8)
        assert large.library == (44, 45, 46, 47)
        assert what_is_left.library == (38, 39)

    def test_freeing_a_context_without_a_block_does_nothing(self):
        """No block taken: nothing to give back."""
        start_reserved_mixer()

        free_block_of(new_inner_context())

        assert unreserved_channel_ids() == list(range(36, 44))

    def test_a_block_of_no_channels_holds_nothing(self):
        """Neither a live pool nor library channels: an empty block, nothing grows."""
        start_reserved_mixer()

        empty = block_in(new_inner_context(), live_pool=0, library_channels=0)

        assert empty == ChannelPartition(live=(), library=(), legacy_count=8)
        assert pygame.mixer.get_num_channels() == 44

    def test_without_a_mixer_a_block_is_empty_and_not_kept(self):
        """No mixer: the empty partition, and a later call (with a mixer) takes the block."""
        stop_mixer()
        context = new_inner_context()

        without_a_mixer = block_in(context)
        start_reserved_mixer()
        with_a_mixer = block_in(context)

        assert without_a_mixer == ChannelPartition(live=(), library=(), legacy_count=0)
        assert with_a_mixer.library == tuple(range(36, 68))

    def test_a_negative_size_is_refused(self):
        """Each size is a number of channels."""
        start_reserved_mixer()

        with pytest.raises(ValueError, match='library_channels'):
            block_in(new_inner_context(), live_pool=1, library_channels=-1)

    def test_blocks_on_an_unpartitioned_mixer_start_at_channel_zero(self):
        """No default partition: the first block starts at 0, legacy above it."""
        start_mixer(channels=2)
        release_channels()

        block = block_in(new_inner_context(), live_pool=1, library_channels=2)

        assert block == ChannelPartition(live=(2,), library=(0, 1), legacy_count=8)
        assert unreserved_channel_ids() == list(range(3, 11))

    def test_a_restarted_mixer_lays_its_blocks_out_afresh(self):
        """A block from before a restart is forgotten: freeing it frees nothing new."""
        start_reserved_mixer()
        before_the_restart = new_inner_context(name='before')
        block_in(before_the_restart)
        start_reserved_mixer()
        after_the_restart = block_in(new_inner_context(name='after'))

        free_block_of(before_the_restart)
        next_block = block_in(new_inner_context(name='next'))

        assert after_the_restart.library == tuple(range(36, 68))
        assert next_block.library == tuple(range(72, 104))

    def test_releasing_the_channels_forgets_every_block(self):
        """Shutdown's release: nothing reserved, and the next block is laid out afresh.

        The mixer keeps its 80 channels (it never shrinks), so the new partition leaves 44
        legacy channels, and the block keeps as many above it.
        """
        start_reserved_mixer()
        block_in(new_inner_context(name='before'))

        release_channels()
        released = unreserved_channel_ids()
        partition = reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)
        block = block_in(new_inner_context(name='after'))

        assert released == list(range(80))
        assert partition.legacy_count == 44
        assert block.library == tuple(range(36, 68))
        assert block.legacy_count == 44
        assert unreserved_channel_ids() == list(range(72, 116))

    def test_plain_plays_never_land_on_a_block(self):
        """With every legacy channel busy, a plain play finds none: never a block's channel."""
        start_reserved_mixer()
        block = block_in(new_inner_context())
        legacy_sound = pygame.mixer.Sound(buffer=bytes(44100 * 4))

        channels = [legacy_sound.play() for _ in range(8)]
        ninth = legacy_sound.play()
        block_busy = [
            pygame.mixer.Channel(index).get_busy() for index in (*block.library, *block.live)
        ]

        assert sorted(channel.id for channel in channels) == list(range(72, 80))
        assert ninth is None
        assert not any(block_busy)

    def test_a_default_partition_with_blocks_held_keeps_them_reserved(self, mocker):
        """A second default partition of the same sizes: same channels, the blocks kept."""
        start_reserved_mixer()
        block_in(new_inner_context())
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

        partition = reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)

        assert partition == ChannelPartition(
            live=(0, 1, 2, 3), library=tuple(range(4, 36)), legacy_count=8
        )
        set_num_channels.assert_not_called()
        assert unreserved_channel_ids() == list(range(72, 80))

    def test_a_default_partition_over_a_held_block_is_refused(self):
        """Its library would take a tile's channels: refused, naming both."""
        start_reserved_mixer()
        block_in(new_inner_context())

        with pytest.raises(ChannelsHeldError, match=r'channels 0-39.*from channel 36'):
            reserve_channels(live_pool=4, library_channels=36, legacy_channels=8)

    def test_a_default_partition_over_freed_blocks_lays_them_out_afresh(self):
        """Nothing held: the larger partition is made, the next block above it."""
        start_reserved_mixer()
        finished = new_inner_context(name='finished')
        block_in(finished)
        free_block_of(finished)

        partition = reserve_channels(live_pool=4, library_channels=40, legacy_channels=8)
        block = block_in(new_inner_context(name='next'), live_pool=1, library_channels=1)

        assert partition.library == tuple(range(4, 44))
        assert block == ChannelPartition(live=(45,), library=(44,), legacy_count=36)

    def test_the_snapshot_shows_the_legacy_channels_above_the_blocks(self):
        """The default table's legacy channels are the mixer's unreserved ones, 72-79."""
        partition = start_reserved_mixer()
        block_in(new_inner_context())
        table = make_table(partition)

        legacy = [state.index for state in table.snapshot() if state.group == 'legacy']

        assert legacy == list(range(72, 80))

    def test_a_heard_tile_and_the_default_context_never_steal_each_others_channels(self):
        """The collision Task 2 found: both play a voice to its end, each on its own channel."""
        partition = start_reserved_mixer()
        default_table = make_table(partition, buses=unreserved_buses())
        context = new_inner_context()
        block = block_in(context)
        with context.active():
            set_audible(audible=True)
            tile_table = make_table(block, buses=unreserved_buses())
            tile_handle = tile_table.play(
                baked_sound(seconds=2.0), owner=GAME_SCENE, **PLAY_DEFAULTS
            )
        default_handle = default_table.play(
            baked_sound(seconds=2.0), owner=GAME_SCENE, **PLAY_DEFAULTS
        )
        tile_channel = pygame.mixer.Channel(block.library[tile_handle.slot])
        default_channel = pygame.mixer.Channel(partition.library[default_handle.slot])
        tile_sound = tile_channel.get_sound()
        default_sound = default_channel.get_sound()
        seen = []
        for _ in range(119):
            seen.extend((
                (tile_handle.is_playing, default_handle.is_playing),
                (tile_channel.get_sound(), default_channel.get_sound()),
            ))
            with context.active():
                advance_frames(tile_table, count=1)
            default_table.advance(dt=FRAME_SECONDS, paused_owners=frozenset())
        with context.active():
            advance_frames(tile_table, count=1)
        default_table.advance(dt=FRAME_SECONDS, paused_owners=frozenset())
        ended = (tile_handle.is_playing, default_handle.is_playing)
        pygame.mixer.stop()

        assert ended == (False, False)
        assert tile_channel.id != default_channel.id
        assert tile_channel.id in block.library
        assert default_channel.id in partition.library
        assert tile_sound is not None
        assert default_sound is not None
        assert seen == [(True, True), (tile_sound, default_sound)] * 119
        assert tile_table.counters.steals == default_table.counters.steals == 0
