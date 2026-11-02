"""Tests for sound handles: generations, stop, cancel, release, volume and pan (impl spec 4.4)."""

import dataclasses
import itertools
import math

import pygame
import pytest

from glitchygames.audio.voices import SoundHandle, constant_power_gains
from tests.audio.library_support import stop_mixer
from tests.audio.voice_support import (
    FRAME_SECONDS,
    GAME_SCENE,
    PLAY_DEFAULTS,
    RecordingChannel,
    advance_frames,
    baked_sound,
    calls_named,
    make_table,
    start_reserved_mixer,
    unreserved_buses,
)


@pytest.fixture(autouse=True)
def _mixer_stopped_afterwards():
    """Stop the mixer after each test so the harness restarts it with the run's format."""
    yield
    stop_mixer()


@pytest.fixture
def table():
    """A voice table over one library channel, without reservations.

    Returns:
        The table.
    """
    partition = start_reserved_mixer(live_pool=0, library_channels=1, legacy_channels=8)
    return make_table(partition, buses=unreserved_buses())


@pytest.fixture
def channel_calls(mocker):
    """Record every call the voice table makes on a mixer channel (the channels stay real).

    Returns:
        The list of (channel index, call, arguments).
    """
    RecordingChannel.calls.clear()
    mocker.patch('pygame.mixer.Channel', RecordingChannel)
    return RecordingChannel.calls


def test_stale_handles_return_false_after_the_slot_is_reused(table):
    """A handle never controls the voice that later took its slot (generation counters)."""
    short_sound = baked_sound(seconds=0.05)
    first = table.play(short_sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    advance_frames(table, count=3)
    pygame.mixer.Channel(0).stop()  # the device has finished it too
    second = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert second.slot == first.slot
    assert second.generation != first.generation
    assert [
        first.is_playing,
        first.stop(),
        first.cancel(),
        first.release(),
        first.set_volume(0.5),
        first.set_pan(0.5),
    ] == [False] * 6
    assert second.is_playing is True


def test_a_handle_is_its_slot_and_generation():
    """Handles are frozen values: equal and hashing by (slot, generation), never by table."""
    handle = SoundHandle(slot=3, generation=7, table=None)

    assert handle == SoundHandle(slot=3, generation=7)
    assert hash(handle) == hash(SoundHandle(slot=3, generation=7, table=None))
    assert 'table' not in repr(handle)
    with pytest.raises(dataclasses.FrozenInstanceError):
        handle.slot = 4  # ty: ignore[invalid-assignment]


def test_stopping_twice_is_harmless(table, channel_calls):
    """The first stop fades and returns True; the second does nothing and returns False."""
    handle = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert handle.stop() is True
    assert handle.stop() is False
    assert calls_named(channel_calls, 'fadeout') == [(0, (50,))]


@pytest.mark.parametrize(('fade', 'milliseconds'), [(0.0, 5), (0.001, 5), (0.2, 200)])
def test_a_stop_fades_for_at_least_five_ms(table, channel_calls, fade, milliseconds):
    """stop(fade=...) fades over the fade, never under 5 ms (feature spec Lifecycle)."""
    handle = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)

    handle.stop(fade=fade)

    assert calls_named(channel_calls, 'fadeout') == [(0, (milliseconds,))]


def test_a_negative_fade_is_refused(table):
    """Fades are durations."""
    handle = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)

    with pytest.raises(ValueError, match='fade'):
        handle.stop(fade=-1.0)
    with pytest.raises(ValueError, match='fade'):
        handle.set_volume(0.5, fade=-1.0)


def test_cancel_is_a_five_ms_declick(table, channel_calls):
    """cancel() fades over 5 ms; the channel is free once 5 ms of frame time have passed."""
    handle = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert handle.cancel() is True
    assert handle.is_playing is False
    assert calls_named(channel_calls, 'fadeout') == [(0, (5,))]
    assert table.snapshot()[0].state == 'fading'
    advance_frames(table, count=1)
    assert table.snapshot()[0].state == 'idle'


def test_stopping_a_paused_voice_stops_its_channel_at_once(table, channel_calls):
    """A paused channel cannot fade; it is silent, so it is stopped and freed."""
    handle = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)
    advance_frames(table, count=1, paused_owners={GAME_SCENE})

    assert handle.stop() is True
    assert calls_named(channel_calls, 'stop') == [(0, ())]
    assert calls_named(channel_calls, 'fadeout') == []
    assert table.snapshot()[0].state == 'idle'


def test_release_on_a_non_looping_baked_sound_returns_false(table):
    """Its release is already part of its audio: nothing happens."""
    handle = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert handle.release() is False
    assert handle.is_playing is True


def test_release_on_a_looping_sound_ends_it_after_the_current_pass(table, channel_calls):
    """The loop fades out over what is left of the pass and ends exactly at the pass's end."""
    loop_sound = baked_sound(seconds=0.5)
    handle = table.play(loop_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'loop': True}))
    advance_frames(table, count=42)  # 0.7 s: 0.2 s into the second pass

    assert handle.release() is True
    assert handle.release() is True
    assert calls_named(channel_calls, 'fadeout') == [(0, (300,))]
    advance_frames(table, count=17)
    assert handle.is_playing is True
    advance_frames(table, count=1)
    assert handle.is_playing is False
    assert table.snapshot()[0].state == 'idle'
    assert handle.release() is False


def test_releasing_a_paused_loop_fades_once_it_resumes(table, channel_calls):
    """A paused channel cannot fade, so the release's fade starts when the voice resumes."""
    loop_sound = baked_sound(seconds=0.5)
    handle = table.play(loop_sound, owner=GAME_SCENE, **(PLAY_DEFAULTS | {'loop': True}))
    advance_frames(table, count=6)
    advance_frames(table, count=10, paused_owners={GAME_SCENE})  # 7 frames played in all

    assert handle.release() is True
    no_fade_while_paused = calls_named(channel_calls, 'fadeout')
    advance_frames(table, count=1)

    assert no_fade_while_paused == []
    remaining_milliseconds = round((0.5 - 7 * FRAME_SECONDS) * 1000)
    assert calls_named(channel_calls, 'fadeout') == [(0, (remaining_milliseconds,))]
    assert [kind for _, kind, _ in channel_calls][-2:] == ['unpause', 'fadeout']


def test_set_volume_applies_at_once_without_a_fade(table, channel_calls):
    """The new volume reaches the channel immediately, with the voice's pan."""
    handle = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)
    channel_calls.clear()

    assert handle.set_volume(0.25) is True

    left, right = calls_named(channel_calls, 'set_volume')[0][1]
    expected = constant_power_gains(pan=0.0, gain=0.25)
    assert math.isclose(left, expected[0])
    assert math.isclose(right, expected[1])


def test_set_volume_with_a_fade_steps_once_per_frame(table, channel_calls):
    """A 0.1 s fade from 1.0 to 0.0 takes six frame steps, each lower, ending at zero."""
    handle = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)
    channel_calls.clear()

    assert handle.set_volume(0.0, fade=0.1) is True
    advance_frames(table, count=8)

    lefts = [float(arguments[0]) for _, arguments in calls_named(channel_calls, 'set_volume')]
    assert len(lefts) == 6
    assert all(later < earlier for earlier, later in itertools.pairwise(lefts))
    assert math.isclose(lefts[0], math.sqrt(0.5) * (1 - 1 / 6))
    assert lefts[-1] == 0.0


def test_a_new_volume_fade_starts_from_where_the_last_one_got_to(table, channel_calls):
    """Mid-fade, a new fade starts from the volume reached, not the old target."""
    handle = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)
    handle.set_volume(0.0, fade=0.1)
    advance_frames(table, count=3)  # half way: 0.5
    channel_calls.clear()

    handle.set_volume(1.0, fade=FRAME_SECONDS * 2)
    advance_frames(table, count=1)

    left = calls_named(channel_calls, 'set_volume')[0][1][0]
    assert math.isclose(left, math.sqrt(0.5) * 0.75)


def test_set_pan_moves_the_voice(table, channel_calls):
    """Pan +1 sends everything right."""
    handle = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)
    channel_calls.clear()

    assert handle.set_pan(1.0) is True

    left, right = calls_named(channel_calls, 'set_volume')[0][1]
    assert math.isclose(left, 0.0, abs_tol=1e-12)
    assert math.isclose(right, 1.0)


def test_invalid_volume_and_pan_on_a_handle_are_value_errors(table):
    """The handle checks its arguments as play does."""
    handle = table.play(baked_sound(seconds=1.0), owner=GAME_SCENE, **PLAY_DEFAULTS)

    with pytest.raises(ValueError, match='volume'):
        handle.set_volume(2.0)
    with pytest.raises(ValueError, match='pan'):
        handle.set_pan(-1.5)


def test_a_waiting_play_can_be_controlled_before_it_starts(table, channel_calls):
    """A play waiting for its stolen channel is a live voice: stop it and it never starts."""
    sound = baked_sound(seconds=1.0)
    table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS)
    waiting = table.play(sound, owner=GAME_SCENE, **PLAY_DEFAULTS)

    assert waiting.set_volume(0.5) is True
    assert waiting.set_pan(0.5) is True
    assert waiting.stop() is True
    advance_frames(table, count=1)

    assert len(calls_named(channel_calls, 'play')) == 1
    assert table.snapshot()[0].state == 'idle'
