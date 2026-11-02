"""Tests for the voice table: allocation, stealing, time, pause, buses and pan (impl spec 7)."""

import logging
import math

import numpy as np
import pygame
import pytest

from glitchygames.audio.buses import BusTree
from glitchygames.audio.voices import VoiceCounters, constant_power_gains
from tests.audio.library_support import stop_mixer
from tests.audio.voice_support import (
    FRAME_SECONDS,
    GAME_SCENE,
    OTHER_SCENE,
    PLAY_DEFAULTS,
    RecordingChannel,
    advance_frames,
    baked_sound,
    calls_named,
    make_table,
    start_reserved_mixer,
    unreserved_buses,
)

ONE_SECOND_SOUND_SECONDS = 1.0


@pytest.fixture(autouse=True)
def _mixer_stopped_afterwards():
    """Stop the mixer after each test so the harness restarts it with the run's format."""
    yield
    stop_mixer()


@pytest.fixture
def partition():
    """The default partition (4 live, 32 library, 8 legacy) on a fresh stereo mixer.

    Returns:
        The partition.
    """
    return start_reserved_mixer()


@pytest.fixture
def table(partition):
    """A voice table over the default partition and the default buses.

    Returns:
        The table.
    """
    return make_table(partition)


@pytest.fixture
def channel_calls(mocker):
    """Record every call the voice table makes on a mixer channel (the channels stay real).

    Returns:
        The list of (channel index, call, arguments).
    """
    RecordingChannel.calls.clear()
    mocker.patch('pygame.mixer.Channel', RecordingChannel)
    return RecordingChannel.calls


@pytest.fixture
def one_second_sound():
    """A sound exactly one second long.

    Returns:
        The sound.
    """
    return baked_sound(seconds=ONE_SECOND_SOUND_SECONDS)


# --- Pan ---


def test_constant_power_pan_keeps_power_within_a_tenth_of_a_db():
    """left² + right² is the same everywhere across the pan range (impl spec 7.2)."""
    powers = [
        sum(side**2 for side in constant_power_gains(pan=pan, gain=1.0))
        for pan in np.linspace(-1, 1, 21)
    ]

    assert 10 * np.log10(max(powers) / min(powers)) <= 0.1


def test_constant_power_pan_is_minus_three_db_at_the_centre_and_one_sided_at_the_ends():
    """θ = (pan + 1)·π/4: centre is cos(π/4) on both sides, the ends one side only."""
    left, right = constant_power_gains(pan=0.0, gain=1.0)
    hard_left = constant_power_gains(pan=-1.0, gain=0.5)
    hard_right = constant_power_gains(pan=1.0, gain=0.5)

    assert math.isclose(left, math.sqrt(0.5))
    assert math.isclose(right, math.sqrt(0.5))
    assert math.isclose(hard_left[0], 0.5)
    assert math.isclose(hard_left[1], 0.0, abs_tol=1e-12)
    assert math.isclose(hard_right[0], 0.0, abs_tol=1e-12)
    assert math.isclose(hard_right[1], 0.5)


# --- Allocation ---


def test_a_play_takes_the_lowest_free_library_channel_and_sets_its_gains(
    table, channel_calls, one_second_sound
):
    """Channel(4).play(sound, loops=0), then set_volume(left, right) after it (impl spec 7.2)."""
    table.play(one_second_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'pan': -1.0}))

    assert [(index, kind) for index, kind, _ in channel_calls] == [
        (4, 'play'),
        (4, 'set_volume'),
    ]
    play_arguments = calls_named(channel_calls, 'play')[0][1]
    assert play_arguments[0] is one_second_sound.mixer_sound()
    assert play_arguments[1] == 0
    left, right = calls_named(channel_calls, 'set_volume')[0][1]
    assert math.isclose(left, 1.0)
    assert math.isclose(right, 0.0, abs_tol=1e-12)


def test_a_looping_play_loops_forever_on_the_device(table, channel_calls, one_second_sound):
    """loop=True plays with loops=-1."""
    table.play(one_second_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'loop': True}))

    assert calls_named(channel_calls, 'play')[0][1][1] == -1


def test_every_play_goes_through_compile_for_play(partition):
    """The library compiles (cache none) or touches the LRU (cache ram) at every play."""
    compiled_sound = baked_sound(seconds=0.5, name='compiled')
    requested = []

    def compile_for_play(sound):
        requested.append(sound)
        return compiled_sound

    table = make_table(partition, compile_for_play=compile_for_play)
    asked_for = baked_sound(seconds=0.5, name='asked')

    table.play(asked_for, owner=GAME_SCENE, **PLAY_DEFAULTS)
    table.play(asked_for, owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert requested == [asked_for, asked_for]
    assert table.is_playing_sound(compiled_sound)
    assert not table.is_playing_sound(baked_sound(seconds=0.5, name='other'))


def test_one_sound_played_many_times_is_many_voices(table, one_second_sound):
    """Stopping one play of a sound leaves its other plays alone."""
    handles = [table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS) for _ in range(3)]

    handles[0].stop()

    assert [handle.is_playing for handle in handles[1:]] == [True, True]
    assert handles[0].is_playing is False


def test_a_channel_still_fading_on_the_device_is_skipped(table, one_second_sound):
    """A table-free channel whose device is still busy (a fade) is not used (impl spec 7.1)."""
    first = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    # A five-second fade: the device is still fading when the table's time has run it out
    first.stop(fade=5.0)
    advance_frames(table, count=301)

    second = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert table.snapshot()[4].state == 'idle'
    assert table.snapshot()[5].state == 'playing'
    assert second.slot == 1


def test_an_unknown_bus_is_a_key_error(table, one_second_sound):
    """The bus is looked up in the tree."""
    with pytest.raises(KeyError, match='sfx'):
        table.play(one_second_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'bus': 'sfx'}))


@pytest.mark.parametrize(
    ('argument', 'value'),
    [('volume', -1.0), ('volume', 1.5), ('pan', 3.0), ('pan', math.nan), ('priority', 101)],
)
def test_an_invalid_playback_argument_is_a_value_error(table, one_second_sound, argument, value):
    """Volume 0-1, pan -1-1, priority 0-100; the message names the parameter."""
    with pytest.raises(ValueError, match=argument):
        table.play(one_second_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {argument: value}))


def test_without_a_mixer_a_play_is_a_silent_handle_and_one_warning(caplog, one_second_sound):
    """AUD-FUNC-006: no mixer, no channels: handles answer False and one warning is logged."""
    stop_mixer()
    from glitchygames.audio.voices import reserve_channels

    table = make_table(reserve_channels(live_pool=4, library_channels=32, legacy_channels=8))

    with caplog.at_level(logging.WARNING, logger='game.audio.voices'):
        first = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
        second = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert [first.is_playing, second.is_playing, first.stop(), first.set_pan(0.5)] == [
        False,
        False,
        False,
        False,
    ]
    assert len([record for record in caplog.records if 'no mixer' in record.message]) == 1
    assert table.counters == VoiceCounters(steals=0, delayed_plays=0, dropped_plays=0)


def test_a_sound_without_samples_for_the_mixer_is_silent(table):
    """A sound the compile step left uncompiled has no pygame sound: a silent handle."""
    uncompiled = baked_sound(seconds=0.5)
    uncompiled.release()

    handle = table.play(uncompiled, owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert handle.is_playing is False


# --- Stealing ---


def _steal_run():
    """Fill four channels with a mix of voices, then play more; return what survived.

    Returns:
        Which handles still play, by label, and the table's counters.
    """
    partition = start_reserved_mixer(live_pool=0, library_channels=4, legacy_channels=8)
    table = make_table(partition, buses=unreserved_buses())
    sound = baked_sound(seconds=2.0)
    loop_sound = baked_sound(seconds=0.5)
    handles = {
        'old_low': table.play(sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'priority': 10})),
        'new_low': table.play(sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'priority': 10})),
        'releasing_high': table.play(
            loop_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'priority': 40, 'loop': True})
        ),
        'high': table.play(sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'priority': 60})),
    }
    handles['releasing_high'].release()
    order = []
    for label in ('first', 'second', 'third'):
        handles[label] = table.play(sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'priority': 50}))
        order.append({name: handle.is_playing for name, handle in handles.items()})
    advance_frames(table, count=1)
    return order, table.counters


def test_stealing_is_deterministic_and_prefers_releasing_low_priority_old_voices():
    """AUD-MIX-003: releasing first, then lowest priority, then oldest; never a higher priority."""
    runs = []
    for _ in range(3):
        runs.append(_steal_run())
        stop_mixer()

    assert runs[0] == runs[1] == runs[2]
    order, counters = runs[0]
    assert order[0] == {
        'old_low': True,
        'new_low': True,
        'releasing_high': False,
        'high': True,
        'first': True,
    }
    assert order[1]['old_low'] is False
    assert order[1]['new_low'] is True
    assert order[2]['new_low'] is False
    assert order[2]['high'] is True
    assert counters == VoiceCounters(steals=3, delayed_plays=3, dropped_plays=0)


def test_a_play_nothing_can_be_stolen_for_is_dropped_and_counted():
    """Every voice outranks the new play: it is dropped, never an exception (feature spec 6.2)."""
    partition = start_reserved_mixer(live_pool=0, library_channels=2, legacy_channels=8)
    table = make_table(partition, buses=unreserved_buses())
    sound = baked_sound(seconds=1.0)
    keepers = [
        table.play(sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'priority': 90})) for _ in range(2)
    ]

    dropped = table.play(sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'priority': 20}))

    assert dropped.is_playing is False
    assert dropped.stop() is False
    assert all(handle.is_playing for handle in keepers)
    assert table.counters.dropped_plays == 1


def test_a_stolen_channel_fades_for_ten_ms_and_the_stealer_starts_next_frame(channel_calls):
    """Steal: fadeout(10) and the channel is fading; the waiting play starts on the next advance."""
    partition = start_reserved_mixer(live_pool=0, library_channels=1, legacy_channels=8)
    table = make_table(partition, buses=unreserved_buses())
    sound = baked_sound(seconds=1.0)
    victim = table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    channel_calls.clear()

    stealer = table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert victim.is_playing is False
    assert stealer.is_playing is True
    assert [(index, kind) for index, kind, _ in channel_calls] == [(0, 'fadeout')]
    assert calls_named(channel_calls, 'fadeout')[0][1] == (10,)
    assert table.snapshot()[0].state == 'fading'
    assert table.counters.delayed_plays == 1

    table.advance(dt=FRAME_SECONDS, paused_owners=frozenset())

    assert [kind for _, kind, _ in channel_calls[1:]] == ['play', 'set_volume']
    assert table.snapshot()[0].state == 'playing'
    # The waiting frame is not played time: the voice starts at 0 when it starts
    advance_frames(table, count=59)
    assert stealer.is_playing is True
    advance_frames(table, count=1)
    assert stealer.is_playing is False


def test_a_channel_still_fading_in_the_table_is_not_free_whatever_the_device_says(
    channel_calls,
):
    """R30: a stopped voice's channel is not free until its fade ends in frame time.

    A play steals even when the device has already finished that fade: the table alone decides.
    """
    partition = start_reserved_mixer(live_pool=0, library_channels=2, legacy_channels=8)
    table = make_table(partition, buses=unreserved_buses())
    sound = baked_sound(seconds=1.0)
    stopped = table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    playing = table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    stopped.stop(fade=0.5)
    pygame.mixer.Channel(0).stop()  # the device finished that fade early
    channel_calls.clear()

    newcomer = table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert [playing.is_playing, newcomer.is_playing] == [False, True]
    assert [(index, kind) for index, kind, _ in channel_calls] == [(1, 'fadeout')]
    assert table.counters == VoiceCounters(steals=1, delayed_plays=1, dropped_plays=0)


def test_voices_ended_by_played_time_free_their_channels_while_the_device_still_plays(
    channel_calls,
):
    """R30: voices ended by played time free their channels; nothing is stolen.

    The device is still busy on those channels; the plays take them anyway, cutting at most one
    device buffer of the ended voices' tails.
    """
    partition = start_reserved_mixer(live_pool=0, library_channels=2, legacy_channels=8)
    table = make_table(partition, buses=unreserved_buses())
    sound = baked_sound(seconds=1.0)
    ended = [table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS) for _ in range(2)]
    advance_frames(table, count=60)
    device_busy = [pygame.mixer.Channel(index).get_busy() for index in (0, 1)]
    channel_calls.clear()

    newcomers = [table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS) for _ in range(2)]

    assert device_busy == [True, True]
    assert [handle.is_playing for handle in ended] == [False, False]
    assert [handle.is_playing for handle in newcomers] == [True, True]
    assert [(index, kind) for index, kind, _ in channel_calls] == [
        (0, 'play'),
        (0, 'set_volume'),
        (1, 'play'),
        (1, 'set_volume'),
    ]
    assert table.counters == VoiceCounters(steals=0, delayed_plays=0, dropped_plays=0)


def test_stopped_handles_answer_false_at_once_while_the_channel_fades(table, one_second_sound):
    """R31: is_playing is False right after stop() or cancel(); the channel stays fading."""
    stopped = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    cancelled = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)

    stopped.stop()
    cancelled.cancel()

    assert [stopped.is_playing, cancelled.is_playing] == [False, False]
    assert [state.state for state in table.snapshot()[4:6]] == ['fading', 'fading']


def test_a_stealer_its_steal_brings_under_its_reservation_plays_at_once(channel_calls):
    """Impl spec 7.1 step 2: after the steal, a channel its bus may now use is taken at once."""
    partition = start_reserved_mixer(live_pool=0, library_channels=3, legacy_channels=8)
    buses = BusTree()
    buses['music'].reserved_channels = 1
    table = make_table(partition, buses=buses)
    sound = baked_sound(seconds=1.0)
    ui_play = PLAY_DEFAULTS | {'bus': 'ui', 'priority': 80}
    clicks = [table.play(sound, owner=GAME_SCENE, **ui_play) for _ in range(2)]
    channel_calls.clear()

    # ui is at its reservation and the free channel is music's, so the third click steals the
    # oldest click; ui is then under its reservation and may take the free channel at once
    third = table.play(sound, owner=GAME_SCENE, **ui_play)

    assert [clicks[0].is_playing, clicks[1].is_playing, third.is_playing] == [False, True, True]
    assert [(index, kind) for index, kind, _ in channel_calls] == [
        (0, 'fadeout'),
        (2, 'play'),
        (2, 'set_volume'),
    ]
    assert table.counters == VoiceCounters(steals=1, delayed_plays=0, dropped_plays=0)
    assert [state.state for state in table.snapshot()[:3]] == ['fading', 'playing', 'playing']


def test_the_ui_reservation_is_never_starved_by_an_effects_storm(table):
    """100 effects plays at top priority still leave ui (and music) their reserved channels."""
    sound = baked_sound(seconds=1.0)
    storm = [
        table.play(sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'priority': 100}))
        for _ in range(100)
    ]

    click = table.play(sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'bus': 'ui', 'priority': 80}))
    second_click = table.play(
        sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'bus': 'ui', 'priority': 80})
    )
    music = table.play(
        sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'bus': 'music', 'priority': 90})
    )

    # 28 voices take the channels left over, 28 more steal them (waiting a frame), then nothing
    # playing is left to steal and the remaining 44 are dropped
    assert sum(handle.is_playing for handle in storm) == 28
    assert [click.is_playing, second_click.is_playing, music.is_playing] == [True, True, True]
    assert table.counters == VoiceCounters(steals=28, delayed_plays=28, dropped_plays=44)


def test_a_voice_on_a_bus_at_its_reservation_is_not_stolen_by_another_bus():
    """Stealing a ui voice would drop ui under its reservation, so an effects play is dropped."""
    partition = start_reserved_mixer(live_pool=0, library_channels=2, legacy_channels=8)
    buses = BusTree()
    buses['music'].reserved_channels = 0
    table = make_table(partition, buses=buses)
    sound = baked_sound(seconds=1.0)
    clicks = [
        table.play(sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'bus': 'ui', 'priority': 0}))
        for _ in range(2)
    ]

    effect = table.play(sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'priority': 100}))

    assert effect.is_playing is False
    assert all(handle.is_playing for handle in clicks)
    assert table.counters.dropped_plays == 1


# --- Time, pause and silence ---


def test_is_playing_follows_played_time_not_the_device(table, one_second_sound):
    """A one-second voice plays for exactly 60 frames of 1/60 s, whatever the device says."""
    handle = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    pygame.mixer.Channel(4).stop()

    advance_frames(table, count=59)
    still_playing = handle.is_playing
    advance_frames(table, count=1)

    assert still_playing is True
    assert handle.is_playing is False
    assert table.snapshot()[4].state == 'idle'


def test_a_paused_voice_is_never_reaped_or_reused(table, one_second_sound, channel_calls):
    """Impl spec 7.3: a paused owner's voice keeps its channel and place while it waits."""
    handle = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)

    advance_frames(table, count=300, paused_owners={GAME_SCENE})
    other = table.play(one_second_sound, owner=OTHER_SCENE, **PLAY_DEFAULTS)

    assert handle.is_playing
    assert other.slot != handle.slot
    assert table.snapshot()[4].state == 'paused'
    assert calls_named(channel_calls, 'pause') == [(4, ())]


def test_a_paused_voice_is_never_stolen():
    """Stealing considers playing voices only; a held voice keeps its channel."""
    partition = start_reserved_mixer(live_pool=0, library_channels=1, legacy_channels=8)
    table = make_table(partition, buses=unreserved_buses())
    sound = baked_sound(seconds=1.0)
    held = table.play(sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'priority': 0}))
    advance_frames(table, count=1, paused_owners={GAME_SCENE})

    newcomer = table.play(sound, owner=OTHER_SCENE, **(PLAY_DEFAULTS | {'priority': 100}))

    assert held.is_playing is True
    assert newcomer.is_playing is False
    assert table.counters.dropped_plays == 1


def test_a_resumed_voice_plays_out_its_remaining_time(table, one_second_sound, channel_calls):
    """Pause stops the voice's time; resume unpauses the channel and the time goes on."""
    handle = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    advance_frames(table, count=30)
    advance_frames(table, count=100, paused_owners={GAME_SCENE})

    advance_frames(table, count=1)
    advance_frames(table, count=28)
    before_end = handle.is_playing
    advance_frames(table, count=1)

    assert before_end is True
    assert handle.is_playing is False
    assert calls_named(channel_calls, 'unpause') == [(4, ())]


def test_silenced_ends_the_voice_on_that_channel(table, one_second_sound):
    """FrameSilencer stopped the channel; silenced() ends its voice in the table (impl 7.3)."""
    handle = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    other = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    pygame.mixer.Channel(4).stop()

    table.silenced(4)
    table.silenced(0)
    table.silenced(40)

    assert handle.is_playing is False
    assert other.is_playing is True
    assert table.snapshot()[4].state == 'idle'


def test_a_silenced_fading_or_waiting_channel_is_idle(channel_calls):
    """A channel the silencer stopped is idle whatever it was doing, waiting play included."""
    partition = start_reserved_mixer(live_pool=0, library_channels=1, legacy_channels=8)
    table = make_table(partition, buses=unreserved_buses())
    sound = baked_sound(seconds=1.0)
    table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    waiting = table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS)

    table.silenced(0)
    table.advance(dt=FRAME_SECONDS, paused_owners=frozenset())

    assert waiting.is_playing is False
    assert table.snapshot()[0].state == 'idle'
    assert len(calls_named(channel_calls, 'play')) == 1


def test_a_waiting_play_of_a_paused_owner_starts_paused(channel_calls):
    """A play waiting for its stolen channel starts on the next advance, paused if its owner is."""
    partition = start_reserved_mixer(live_pool=0, library_channels=1, legacy_channels=8)
    table = make_table(partition, buses=unreserved_buses())
    sound = baked_sound(seconds=1.0)
    table.play(sound, owner=OTHER_SCENE, **PLAY_DEFAULTS)
    waiting = table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS)

    advance_frames(table, count=100, paused_owners={GAME_SCENE})

    assert waiting.is_playing is True
    assert table.snapshot()[0].state == 'paused'
    assert [kind for _, kind, _ in channel_calls][-3:] == ['play', 'set_volume', 'pause']


# --- Owners and shutdown ---


def test_stop_owner_fades_its_voices_but_not_persisting_ones(
    table, one_second_sound, channel_calls
):
    """Scene clean-up: the owner's voices fade over 50 ms; persist=True voices play on."""
    scene_voice = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    persisting = table.play(
        one_second_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'persist': True})
    )
    other_scene = table.play(one_second_sound, owner=OTHER_SCENE, **PLAY_DEFAULTS)

    table.stop_owner(GAME_SCENE)

    assert [scene_voice.is_playing, persisting.is_playing, other_scene.is_playing] == [
        False,
        True,
        True,
    ]
    assert calls_named(channel_calls, 'fadeout') == [(4, (50,))]
    assert table.snapshot()[4].state == 'fading'
    advance_frames(table, count=3)
    assert table.snapshot()[4].state == 'idle'


def test_close_fades_every_voice_and_refuses_later_plays(table, one_second_sound, channel_calls):
    """Shutdown fades all voices, persisting ones too; plays after close are silent."""
    handles = [
        table.play(one_second_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'persist': True})),
        table.play(one_second_sound, owner=None, **PLAY_DEFAULTS),
    ]

    table.close()
    late = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert [handle.is_playing for handle in handles] == [False, False]
    assert late.is_playing is False
    assert calls_named(channel_calls, 'fadeout') == [(4, (50,)), (5, (50,))]
    assert table.counters.dropped_plays == 0


def test_is_playing_sound_spares_fading_sounds_from_eviction(table, one_second_sound):
    """The device still reads a fading voice's samples, so the library must not drop them."""
    handle = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    handle.stop(fade=0.05)

    fading = table.is_playing_sound(one_second_sound)
    advance_frames(table, count=3)

    assert fading is True
    assert table.is_playing_sound(one_second_sound) is False


# --- Buses ---


def test_bus_volume_applies_to_playing_channels(partition, channel_calls, one_second_sound):
    """A bus change re-applies left/right gains to that bus's playing voices on the next advance."""
    buses = BusTree()
    table = make_table(partition, buses=buses)
    table.play(one_second_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'volume': 0.8}))
    table.play(one_second_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'bus': 'ui'}))
    channel_calls.clear()

    buses['effects'].volume = 0.5
    table.advance(dt=FRAME_SECONDS, paused_owners=frozenset())
    table.advance(dt=FRAME_SECONDS, paused_owners=frozenset())

    volume_calls = calls_named(channel_calls, 'set_volume')
    assert [index for index, _ in volume_calls] == [4, 5]
    expected = constant_power_gains(pan=0.0, gain=0.8 * 0.5)
    assert all(map(math.isclose, volume_calls[0][1], expected, strict=True))
    unchanged = constant_power_gains(pan=0.0, gain=1.0)
    assert all(map(math.isclose, volume_calls[1][1], unchanged, strict=True))


def test_solo_mutes_non_soloed_siblings_on_the_device(partition, channel_calls, one_second_sound):
    """Soloing ui sets the effects voice's gains to zero."""
    buses = BusTree()
    table = make_table(partition, buses=buses)
    table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    table.play(one_second_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'bus': 'ui'}))
    channel_calls.clear()

    buses['ui'].solo = True
    table.advance(dt=FRAME_SECONDS, paused_owners=frozenset())

    gains = dict(calls_named(channel_calls, 'set_volume'))
    assert gains[4] == (0.0, 0.0)
    assert math.isclose(gains[5][0], math.sqrt(0.5))


def test_a_bus_change_reaches_a_paused_voice_too(partition, channel_calls, one_second_sound):
    """A held voice resumes at the bus's new gain: the change reaches its paused channel."""
    buses = BusTree()
    table = make_table(partition, buses=buses)
    table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    advance_frames(table, count=1, paused_owners={GAME_SCENE})
    channel_calls.clear()

    buses['effects'].mute = True
    advance_frames(table, count=1, paused_owners={GAME_SCENE})

    assert channel_calls == [(4, 'set_volume', (0.0, 0.0))]


def test_silencing_an_idle_library_channel_changes_nothing(table, one_second_sound):
    """The silencer stops every channel; an idle one keeps its generation, so handles hold."""
    handle = table.play(one_second_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)

    table.silenced(5)

    assert handle.is_playing is True
    assert table.snapshot()[5].state == 'idle'
