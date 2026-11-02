"""Tests for the live/library/legacy channel partition (impl spec 7.1, AUD-MIX-008)."""

import pygame
import pytest

from glitchygames.audio.live import reserve_live_voice_pool
from glitchygames.audio.voices import ChannelPartition, reserve_channels
from tests.audio.library_support import start_mixer, stop_mixer
from tests.audio.voice_support import (
    GAME_SCENE,
    PLAY_DEFAULTS,
    baked_sound,
    make_table,
    start_reserved_mixer,
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
