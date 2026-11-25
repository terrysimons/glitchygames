"""Tests for live voices' channel and lifecycle (LiveStream) and the live pool (LiveAudio).

Every live voice is a live instrument's (``live_instrument.InstrumentVoice``); its rendering is
tested in tests/audio/test_live_instrument.py. Here a plain live sine plays through the stream:
start, one chunk queued, fades, pause, underruns, the pool's owner rules, live pools per
engine context.
"""

import gc
import logging
import os
import sys
import weakref

import numpy as np
import pygame
import pytest

from glitchygames.audio import live
from glitchygames.audio.effects import Tremolo
from glitchygames.audio.instrument import Filter, Instrument
from glitchygames.audio.live import LiveAudio, LiveStream, LiveVoiceOptions, VoiceState
from glitchygames.audio.live_instrument import InstrumentVoice
from glitchygames.audio.route import set_audible
from glitchygames.audio.voices import (
    constant_power_gains,
    inner_context_partition,
    reserve_inner_game_channels,
)
from glitchygames.engine_context import EngineContext
from glitchygames.process import OutputCapture, run_command
from glitchygames.randomness import numpy_stream, reset_streams
from tests.audio import live_pan_probe
from tests.audio.channel_fade_analysis import RECORDING_TIMEOUT_SECONDS, REPOSITORY_ROOT
from tests.audio.library_support import start_mixer, stop_mixer
from tests.audio.voice_support import LIBRARY_CHANNELS, LIVE_POOL, start_reserved_mixer

RATE = 44100
LIVE_STREAM_TEST_SEED = 78
SINE = Instrument(wave='sine', live=True)


@pytest.fixture
def rendered_chunks(mocker):
    """Capture every chunk the voice renders (to_sound receives the samples).

    Returns:
        The list that collects each rendered chunk.

    """
    chunks = []

    def fake_to_sound(samples, *, volume, side_gains):
        chunks.append(samples)
        return mocker.Mock(name=f'sound{len(chunks)}')

    mocker.patch.object(live, 'to_sound', side_effect=fake_to_sound)
    return chunks


@pytest.fixture
def channel(mocker):
    """A mocked mixer channel that is busy with an empty queue.

    Returns:
        The mocked channel.

    """
    mocked_channel = mocker.Mock(id=0)  # pygame.mixer.Channel.id: the stream reads its table
    mocked_channel.get_queue.return_value = None
    mocked_channel.get_busy.return_value = True
    return mocked_channel


def _voice(channel, **overrides):
    settings = {
        'channel': channel,
        'owner': 'scene',
        'instrument': SINE,
        'frequency': 220.0,
        'volume': 0.5,
        'sample_rate': RATE,
        'random_source': np.random.default_rng(5),
    }
    return InstrumentVoice(**(settings | overrides))


class TestLiveVoiceRandomSource:
    """Where a voice's noise comes from."""

    def test_voice_without_a_random_source_uses_the_live_stream(self, channel):
        """A voice created without random_source draws from numpy_stream('audio.live')."""
        reset_streams(seed=LIVE_STREAM_TEST_SEED)

        voice = _voice(channel, random_source=None)

        assert voice._random_source is numpy_stream('audio.live')


class TestLiveVoiceChunks:
    """Chunk rendering and queuing."""

    def test_start_plays_then_update_queues(self, channel, rendered_chunks):
        stream = _voice(channel).stream
        stream.start()
        channel.play.assert_called_once()
        stream.update()
        channel.queue.assert_called_once()
        assert len(rendered_chunks[0]) == 4410  # 100 ms at 44100 Hz

    def test_update_waits_while_queue_full(self, channel, rendered_chunks):
        stream = _voice(channel).stream
        stream.start()
        channel.get_queue.return_value = object()
        stream.update()
        channel.queue.assert_not_called()

    def test_phase_continuous_across_chunks(self, channel, rendered_chunks):
        stream = _voice(channel, volume=1.0).stream
        stream.start()
        stream.update()
        joined = np.concatenate(rendered_chunks)
        expected = np.sin(2 * np.pi * 220.0 * np.arange(len(joined)) / RATE)
        np.testing.assert_allclose(joined, expected, atol=1e-9)

    def test_filter_and_tremolo_continue_across_chunks(self, channel, rendered_chunks):
        # 177 Hz: the low-pass delays each sawtooth reset by about 50 samples, and at this pitch
        # the delayed resets fall ~125 samples either side of the chunk boundary (233 Hz put
        # one exactly on it, which is a real waveform edge, not a continuity bug)
        motor = Instrument(
            wave='saw',
            live=True,
            filter=Filter('low_pass', 800.0),
            tremolo=Tremolo(rate_hz=7.0, depth=0.5),
        )
        stream = _voice(channel, instrument=motor, volume=1.0, frequency=177.0).stream
        stream.start()
        stream.update()
        boundary_step = abs(rendered_chunks[1][0] - rendered_chunks[0][-1])
        typical_step = np.median(np.abs(np.diff(rendered_chunks[0])))
        assert boundary_step < typical_step * 4


class TestLiveVoiceStopping:
    """Stopping, pausing and underrun recovery."""

    def test_stop_fades_then_drains_without_channel_stop(self, channel, rendered_chunks):
        stream = _voice(channel, volume=1.0).stream
        stream.start()
        stream.stop(fade_out=0.1)
        stream.update()
        assert abs(rendered_chunks[-1][-1]) < 1e-9  # Faded to silence
        assert stream.state is VoiceState.DRAINING
        stream.update()
        assert channel.queue.call_count == 1  # No more chunks after the fade
        channel.stop.assert_not_called()  # stop()/fadeout() would start the queued chunk
        assert stream.is_playing
        channel.get_busy.return_value = False
        assert not stream.is_playing

    def test_stop_now_silences_immediately(self, channel, rendered_chunks):
        stream = _voice(channel).stream
        stream.start()
        stream.stop_now()
        assert channel.stop.call_count == 2  # First starts the queued chunk, second stops it
        assert stream.state is VoiceState.STOPPED

    def test_a_stopped_voice_renders_nothing_more_and_takes_no_settings(
        self, channel, rendered_chunks
    ):
        voice = _voice(channel)
        voice.stream.start()
        voice.stream.stop_now()

        voice.stream.update()

        assert len(rendered_chunks) == 1
        assert not voice.stream.accepts_changes

    def test_stop_before_start_does_nothing(self, channel, rendered_chunks):
        stream = _voice(channel).stream
        assert not stream.stop(fade_out=0.1)
        assert stream.state is VoiceState.IDLE
        stream.start()
        assert stream.state is VoiceState.PLAYING

    def test_fade_longer_than_a_chunk_keeps_fading(self, channel, rendered_chunks):
        stream = _voice(channel, volume=1.0).stream
        stream.start()
        stream.stop(fade_out=0.25)
        stream.update()
        assert stream.state is VoiceState.FADING
        assert abs(rendered_chunks[-1][-1]) > 0.0  # Not silent yet
        channel.get_queue.return_value = None
        stream.update()
        stream.update()
        assert stream.state is VoiceState.DRAINING
        assert abs(rendered_chunks[-1][-1]) < 1e-9

    def test_underrun_recovers(self, channel, rendered_chunks, mocker):
        """Review focus 5: a long hitch drains the channel; the voice restarts."""
        debug = mocker.patch.object(live.log, 'debug')
        stream = _voice(channel).stream
        stream.start()
        channel.get_busy.return_value = False
        stream.update()
        assert debug.called
        assert channel.queue.call_count + channel.play.call_count >= 2

    def test_pause_and_resume(self, channel, rendered_chunks):
        stream = _voice(channel).stream
        stream.start()
        stream.pause()
        channel.pause.assert_called_once()
        stream.update()
        channel.queue.assert_not_called()
        stream.resume()
        channel.unpause.assert_called_once()

    def test_silent_voice_without_channel(self, rendered_chunks):
        stream = _voice(None).stream
        stream.start()
        stream.update()
        stream.stop_now()
        assert not stream.is_playing
        assert rendered_chunks == []


class TestLiveAudio:
    """Pool ownership rules."""

    @pytest.fixture
    def audio(self, mocker, rendered_chunks):
        mocker.patch('pygame.mixer.get_init', return_value=(RATE, -16, 2))
        mocker.patch(
            'pygame.mixer.Channel',
            side_effect=lambda index: mocker.Mock(
                name=f'channel{index}',
                id=index,  # pygame.mixer.Channel.id: the pool keeps channels by it
                get_queue=mocker.Mock(return_value=None),
                get_busy=mocker.Mock(return_value=True),
            ),
        )
        return LiveAudio(channel_indices=(0, 1))

    @staticmethod
    def _create(audio, owner, *, priority=50):
        options = LiveVoiceOptions(priority=priority)
        return audio.create_instrument_voice(
            owner=owner, instrument=SINE, frequency=100.0, options=options
        )

    def test_a_refused_instrument_voice_gives_its_channel_back(self, audio):
        with pytest.raises(ValueError, match='live=True'):
            audio.create_instrument_voice(
                owner='scene', instrument=Instrument(wave='sine'), frequency=100.0
            )

        first, second = self._create(audio, 'scene'), self._create(audio, 'scene')
        assert {first.stream.channel.id, second.stream.channel.id} == {0, 1}

    def test_pool_exhaustion_raises_at_limit_plus_one(self, audio):
        """Full of voices of a higher priority, with nothing it may steal: refused."""
        self._create(audio, 'scene', priority=60)
        self._create(audio, 'scene', priority=60)
        with pytest.raises(ValueError, match='live-voice-pool'):
            self._create(audio, 'scene')

    def test_playing_voice_count(self, audio):
        """playing_voice_count counts only voices that are currently playing."""
        first = self._create(audio, 'scene')
        self._create(audio, 'scene')
        assert audio.playing_voice_count == 0
        first.stream.start()
        assert audio.playing_voice_count == 1

    def test_released_channels_are_reused(self, audio):
        first = self._create(audio, 'scene')
        self._create(audio, 'scene')
        audio.release_voice(first)
        assert self._create(audio, 'scene') is not None

    def test_owner_rules(self, audio):
        active = self._create(audio, 'active').stream
        paused = self._create(audio, 'previous').stream
        active.start()
        paused.start()
        audio.update(active_scene='active', previous_scene='previous', active_transitions=())
        assert paused.state is VoiceState.PAUSED
        audio.update(active_scene='other', previous_scene='active', active_transitions=())
        assert active.state is VoiceState.PAUSED
        assert paused.state is VoiceState.STOPPED  # Abandoned owner: released
        assert self._create(audio, 'new') is not None  # Its channel was freed

    def test_transition_owner_survives_until_transition_ends(self, audio):
        transition = object()
        stream = self._create(audio, transition).stream
        stream.start()
        audio.update(active_scene='new', previous_scene='old', active_transitions=(transition,))
        assert stream.state is VoiceState.PLAYING
        audio.update(active_scene='new', previous_scene='old', active_transitions=(None,))
        assert stream.state is VoiceState.STOPPED

    def test_fading_voice_finishes_when_owner_becomes_previous_scene(self, audio, rendered_chunks):
        stream = self._create(audio, 'scene').stream
        stream.start()
        stream.stop(fade_out=0.1)
        audio.update(active_scene='pause', previous_scene='scene', active_transitions=())
        assert abs(rendered_chunks[-1][-1]) < 1e-9  # The fade chunk was queued
        assert stream.state is VoiceState.DRAINING

    def test_paused_voice_that_is_stopped_renders_its_fade(self, audio, rendered_chunks):
        stream = self._create(audio, 'scene').stream
        stream.start()
        audio.update(active_scene='pause', previous_scene='scene', active_transitions=())
        assert stream.state is VoiceState.PAUSED
        stream.stop(fade_out=0.1)
        audio.update(active_scene='pause', previous_scene='scene', active_transitions=())
        assert abs(rendered_chunks[-1][-1]) < 1e-9
        assert stream.state is VoiceState.DRAINING

    def test_stopped_voice_returns_its_channel_to_the_pool(self, mocker, rendered_chunks):
        mocker.patch('pygame.mixer.get_init', return_value=(RATE, -16, 2))
        mocker.patch('pygame.mixer.Channel', side_effect=lambda index: mocker.Mock(id=index))
        single = LiveAudio(channel_indices=(0,))
        stream = self._create(single, 'scene').stream
        stream.start()
        stream.stop_now()
        single.update(active_scene='scene', previous_scene=None, active_transitions=())
        assert self._create(single, 'scene') is not None

    def test_drained_voice_returns_its_channel_to_the_pool(self, mocker, rendered_chunks):
        mocker.patch('pygame.mixer.get_init', return_value=(RATE, -16, 2))
        drained_channel = mocker.Mock(id=0)
        drained_channel.get_queue.return_value = None
        drained_channel.get_busy.return_value = True
        mocker.patch('pygame.mixer.Channel', return_value=drained_channel)
        single = LiveAudio(channel_indices=(0,))
        stream = self._create(single, 'scene').stream
        stream.start()
        stream.stop(fade_out=0.1)
        single.update(active_scene='scene', previous_scene=None, active_transitions=())
        assert stream.state is VoiceState.DRAINING
        drained_channel.get_busy.return_value = False
        single.update(active_scene='scene', previous_scene=None, active_transitions=())
        assert self._create(single, 'scene') is not None

    def test_releasing_a_voice_twice_is_idempotent(self, audio):
        """The channel goes back once: two more voices fill the pool, a third is refused."""
        first = self._create(audio, 'scene')
        audio.release_voice(first)
        audio.release_voice(first)
        self._create(audio, 'scene', priority=60)
        self._create(audio, 'scene', priority=60)
        with pytest.raises(ValueError, match='live-voice-pool'):
            self._create(audio, 'scene')

    def test_no_mixer_returns_silent_voice(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=None)
        stream = self._create(LiveAudio(channel_indices=()), 'scene').stream
        stream.start()
        assert not stream.is_playing

    def test_no_mixer_warning_is_logged_once(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=None)
        warning = mocker.patch.object(live.log, 'warning')
        audio = LiveAudio(channel_indices=())
        for _ in range(2):
            self._create(audio, 'scene')
        warning.assert_called_once_with('Audio unavailable; live voices are silent')


class TestLiveVoicesOnLivePools:
    """An inner context's live voices on its own live pool (Arcade sub-plan 4, decision 4).

    A silent context's chunks still play, at volume 0, on its own pool: the voice's lifecycle
    reads its channel, so it is the same heard or silent.
    """

    @pytest.fixture(autouse=True)
    def partitioned_mixer(self):
        """Partition a stereo mixer as an outer engine does, declare two inner games; stop it after.

        Yields:
            The default context's partition.
        """
        partition = start_reserved_mixer()
        reserve_inner_game_channels(games=2)
        yield partition
        pygame.mixer.stop()
        stop_mixer()

    @staticmethod
    def _create(audio):
        return audio.create_instrument_voice(owner='scene', instrument=SINE, frequency=220.0)

    def test_a_tiles_live_voice_and_the_default_contexts_get_their_own_channels(
        self, partitioned_mixer
    ):
        """Review Focus 3: both voices are made, on distinct channels, both playing."""
        default_audio = LiveAudio(channel_indices=partitioned_mixer.live)
        tile = EngineContext(name='tile')
        with tile.active():
            set_audible(audible=False)
            block = inner_context_partition(live_pool=4, library_channels=32)
            tile_audio = LiveAudio(channel_indices=block.live)
            tile_stream = self._create(tile_audio).stream
            tile_stream.start()
        default_stream = self._create(default_audio).stream
        default_stream.start()

        busy = [
            index
            for index in range(pygame.mixer.get_num_channels())
            if pygame.mixer.Channel(index).get_busy()
        ]

        assert busy == [partitioned_mixer.live[0], block.live[0]]
        assert tile_stream.is_playing
        assert default_stream.is_playing
        tile_stream.stop_now()
        default_stream.stop_now()

    def test_a_silent_contexts_chunks_play_at_volume_zero_and_a_heard_ones_at_full(
        self, partitioned_mixer
    ):
        """Silent: every chunk at volume 0 on its pool; once heard, the next chunk at 1."""
        tile = EngineContext(name='tile')
        with tile.active():
            set_audible(audible=False)
            block = inner_context_partition(live_pool=4, library_channels=32)
            tile_stream = self._create(LiveAudio(channel_indices=block.live)).stream
            tile_stream.start()
            tile_stream.update()
        tile_channel = pygame.mixer.Channel(block.live[0])
        silent_playing_volume = tile_channel.get_sound().get_volume()
        silent_queued_volume = tile_channel.get_queue().get_volume()
        # Channel.stop() starts the queued chunk (the module's channel facts): twice idles it
        tile_channel.stop()
        tile_channel.stop()
        with tile.active():
            set_audible(audible=True)
        tile_stream.update()
        heard_volume = tile_channel.get_sound().get_volume()

        assert silent_playing_volume == 0.0
        assert silent_queued_volume == 0.0
        assert heard_volume == 1.0
        assert not pygame.mixer.Channel(partitioned_mixer.live[0]).get_busy()
        tile_stream.stop_now()

    def test_releasing_every_voice_stops_them_and_frees_the_pool(self):
        """A finished tile's live voices: stopped, their channels idle and back in the pool."""
        audio = LiveAudio(channel_indices=(0, 1))
        for voice in (self._create(audio), self._create(audio)):
            voice.stream.start()

        audio.release_every_voice()

        assert not pygame.mixer.Channel(0).get_busy()
        assert not pygame.mixer.Channel(1).get_busy()
        assert audio.playing_voice_count == 0
        assert self._create(audio) is not None
        assert self._create(audio) is not None


class TestLiveStreamControls:
    """Bus gain, pan, a held pause, persist and stealing (migration step 7b)."""

    @pytest.fixture
    def chunk_volumes(self, mocker):
        """Capture the volume each chunk plays at.

        Returns:
            The list of volumes.
        """
        volumes = []

        def fake_to_sound(samples, *, volume, side_gains):
            volumes.append(volume)
            return mocker.Mock(name=f'sound{len(volumes)}')

        mocker.patch.object(live, 'to_sound', side_effect=fake_to_sound)
        return volumes

    def test_each_chunk_plays_at_the_bus_gain_read_as_it_is_rendered(self, channel, chunk_volumes):
        gains = iter([0.5, 0.25])
        stream = _voice(channel, options=LiveVoiceOptions(gain_source=lambda: next(gains))).stream

        stream.start()
        stream.update()

        assert chunk_volumes == [0.5, 0.25]

    def test_without_a_bus_a_chunk_plays_at_full_volume(self, channel, chunk_volumes):
        stream = _voice(channel).stream

        stream.start()

        assert chunk_volumes == [1.0]

    def test_a_silent_context_plays_at_zero_whatever_the_bus(self, channel, chunk_volumes):
        tile = EngineContext(name='tile')
        with tile.active():
            set_audible(audible=False)
            stream = _voice(channel, options=LiveVoiceOptions(gain_source=lambda: 0.5)).stream
            stream.start()

        assert chunk_volumes == [0.0]

    def test_a_silent_voice_takes_a_pan_and_does_nothing_with_it(self, rendered_chunks):
        stream = _voice(None).stream

        stream.set_pan(0.5)
        stream.start()

        assert not stream.is_playing

    def test_a_pan_outside_minus_one_to_one_is_refused(self, channel):
        with pytest.raises(ValueError, match='pan'):
            _voice(channel).stream.set_pan(1.5)

    def test_a_held_pause_survives_the_owner_rules_until_resumed(self, mocker, rendered_chunks):
        mocker.patch('pygame.mixer.get_init', return_value=(RATE, -16, 2))
        mocker.patch('pygame.mixer.Channel', side_effect=lambda index: mocker.Mock(id=index))
        pool = LiveAudio(channel_indices=(0,))
        stream = pool.create_instrument_voice(
            owner='scene', instrument=SINE, frequency=100.0
        ).stream
        stream.start()

        stream.hold()
        pool.update(active_scene='scene', previous_scene=None, active_transitions=())
        assert stream.state is VoiceState.PAUSED
        stream.release_hold()

        assert stream.state is VoiceState.PLAYING

    def test_a_persisting_voice_outlives_its_owner_but_pauses_behind_a_pause_screen(
        self, mocker, rendered_chunks
    ):
        """The baked plays' persist: no release when its owner goes; the pause rules hold."""
        mocker.patch('pygame.mixer.get_init', return_value=(RATE, -16, 2))
        mocker.patch(
            'pygame.mixer.Channel',
            side_effect=lambda index: mocker.Mock(
                id=index,
                get_queue=mocker.Mock(return_value=None),
                get_busy=mocker.Mock(return_value=True),
            ),
        )
        pool = LiveAudio(channel_indices=(0, 1))
        ambience = pool.create_instrument_voice(
            owner='forest', instrument=SINE, frequency=100.0, options=LiveVoiceOptions(persist=True)
        ).stream
        footsteps = pool.create_instrument_voice(
            owner='forest', instrument=SINE, frequency=100.0
        ).stream
        ambience.start()
        footsteps.start()

        pool.update(active_scene='pause', previous_scene='forest', active_transitions=())
        assert ambience.state is VoiceState.PAUSED
        pool.update(active_scene='castle', previous_scene=None, active_transitions=())

        assert ambience.state is VoiceState.PLAYING
        assert footsteps.state is VoiceState.STOPPED

    def test_a_full_pool_steals_the_lowest_priority_voice_at_or_below_the_new_one(
        self, mocker, rendered_chunks
    ):
        """Lowest priority first, then the earliest made; none at or below: refused as before."""
        mocker.patch('pygame.mixer.get_init', return_value=(RATE, -16, 2))
        mocker.patch('pygame.mixer.Channel', side_effect=lambda index: mocker.Mock(id=index))
        pool = LiveAudio(channel_indices=(0, 1))

        def make(priority):
            voice = pool.create_instrument_voice(
                owner='scene',
                instrument=SINE,
                frequency=100.0,
                options=LiveVoiceOptions(priority=priority),
            )
            voice.stream.start()
            return voice.stream

        low, high = make(30), make(60)
        stealer = make(50)

        assert low.state is VoiceState.STOPPED
        assert stealer.channel.id == 0
        assert high.state is VoiceState.PLAYING
        with pytest.raises(ValueError, match='live-voice-pool'):
            make(20)
        equal = make(50)  # ties: the earliest made of the lowest (the first stealer) goes
        assert stealer.state is VoiceState.STOPPED
        assert equal.state is VoiceState.PLAYING


# A long chunk, so the chunk playing is still playing when the test plays over it: the queued
# chunk is freed by pygame's re-entrant callback only while the one before it still plays
LONG_CHUNK = LiveVoiceOptions(chunk_seconds=0.5)


def _channel_slots(channel):
    """The Sounds pygame's channel table names for a channel: playing, then queued.

    Returns:
        The named Sounds, None left out.
    """
    return [sound for sound in (channel.get_sound(), channel.get_queue()) if sound is not None]


def _assert_the_stream_holds_every_chunk_its_channel_names(stream):
    """The invariant: the table never holds the last reference to a stream's chunk, bounded."""
    held = stream.held_chunks
    for named in _channel_slots(stream.channel):
        assert any(named is chunk for chunk in held), 'a chunk on the channel is not held'
    assert len(held) <= live.MAXIMUM_HELD_CHUNKS


class TestLiveStreamKeepsItsChunks:
    """A live voice holds every chunk it plays or queues until its channel has moved past it.

    pygame-ce 2.5.8's mixer frees a queued Sound twice when ``Channel.play`` lands on a channel
    still playing one chunk with another queued and pygame's table holds the only references
    (bugs/2026-11-24-pygame-mixer-frees-a-queued-sound-twice.md; docs/quality/upstream_issues.md).
    Real mixer on the dummy driver: the bug is in pygame's C table, which no mock has.
    """

    @pytest.fixture(autouse=True)
    def mixer(self):
        """A partitioned stereo mixer on the dummy driver, stopped after.

        Yields:
            The partition.
        """
        yield start_reserved_mixer()
        if pygame.mixer.get_init() is not None:
            pygame.mixer.stop()
        stop_mixer()

    def test_a_voice_started_over_another_voices_queued_chunk_frees_no_chunk_too_soon(self):
        """The golden test's hand-off: a second voice starts on a channel the first left playing.

        The first voice's playing and queued chunks must still be alive after the second
        voice's ``Channel.play``: before the fix pygame freed the queued one inside that call.
        """
        channel = pygame.mixer.Channel(0)
        first = _voice(channel, options=LONG_CHUNK)
        first.stream.start()
        first.stream.update()
        queued = channel.get_queue()
        assert queued is not None, 'the first chunk must still be playing, one queued'
        freed = []
        watch = weakref.ref(queued, lambda _reference: freed.append(True))
        del queued

        second = _voice(channel, options=LONG_CHUNK)
        second.stream.start()

        assert freed == []
        assert watch() is not None
        assert first.stream.state is VoiceState.PLAYING
        second.stream.stop_now()
        first.stream.stop_now()

    def test_every_chunk_on_the_channel_is_held_by_the_voice_at_each_step(self):
        """Start, queue, the queue promoted, an underrun's restart, then stop_now: held, bounded."""
        channel = pygame.mixer.Channel(0)
        stream = _voice(channel, options=LONG_CHUNK).stream

        stream.start()
        _assert_the_stream_holds_every_chunk_its_channel_names(stream)
        stream.update()  # one chunk queued
        _assert_the_stream_holds_every_chunk_its_channel_names(stream)
        channel.stop()  # the queued chunk starts (the module's channel facts)
        stream.update()  # the one it moved past is let go, a new one queued
        _assert_the_stream_holds_every_chunk_its_channel_names(stream)
        assert len(stream.held_chunks) == 2
        channel.stop()
        channel.stop()  # idle: an underrun
        stream.update()  # restarts on the idle channel
        _assert_the_stream_holds_every_chunk_its_channel_names(stream)
        assert len(stream.held_chunks) == 1
        stream.stop_now()

        assert stream.held_chunks == ()
        assert _channel_slots(channel) == []

    def test_a_draining_voice_lets_go_of_the_chunks_its_channel_has_finished(self):
        """A drained voice's update keeps nothing the channel no longer names."""
        channel = pygame.mixer.Channel(0)
        stream = _voice(channel, options=LONG_CHUNK).stream
        stream.start()
        stream.stop(fade_out=0.01)
        stream.update()  # the fade is rendered into the queued chunk: draining
        assert stream.state is VoiceState.DRAINING
        channel.stop()
        channel.stop()

        stream.update()

        assert stream.held_chunks == ()

    def test_a_voice_dropped_while_playing_stops_its_channel_before_letting_go(self, monkeypatch):
        """No one stopped it: its chunks go only once its channel names none of them.

        Its finalizer finishes without raising and reports the missing release through the log,
        which the harness reads.
        """
        unraisable = []
        monkeypatch.setattr(sys, 'unraisablehook', unraisable.append)
        channel = pygame.mixer.Channel(0)
        voice = _voice(channel, options=LONG_CHUNK)
        voice.stream.start()
        voice.stream.update()
        queued = channel.get_queue()
        assert queued is not None
        slots_when_freed = []
        watch = weakref.ref(
            queued, lambda _reference: slots_when_freed.append(len(_channel_slots(channel)))
        )
        del queued

        del voice
        gc.collect()

        assert watch() is None
        assert slots_when_freed == [0]
        assert not channel.get_busy()
        assert unraisable == []
        assert [
            (report.stream_name, report.held_chunk_count)
            for report in live.take_unreleased_live_stream_reports()
        ] == [('str on channel 0', 2)]

    def test_a_voice_dropped_after_the_mixer_quit_lets_go_without_the_mixer(self, monkeypatch):
        """A quit mixer has no table left: the chunks simply go, and nothing raises."""
        unraisable = []
        monkeypatch.setattr(sys, 'unraisablehook', unraisable.append)
        voice = _voice(pygame.mixer.Channel(0), options=LONG_CHUNK)
        voice.stream.start()
        held = weakref.ref(voice.stream.held_chunks[0])
        pygame.mixer.stop()
        stop_mixer()

        del voice
        gc.collect()

        assert held() is None
        assert unraisable == []
        assert len(live.take_unreleased_live_stream_reports()) == 1

    def test_a_voice_dropped_after_a_mixer_restart_lets_go_without_reading_the_table(
        self, monkeypatch
    ):
        """A restarted mixer's table is 8 long: a pool channel past it is never read.

        pygame reads its table unchecked, so the read would be past the table's end: a crash, or
        garbage taken for a Sound, by luck. Nothing raises and the chunks go.
        """
        unraisable = []
        monkeypatch.setattr(sys, 'unraisablehook', unraisable.append)
        voice = _voice(pygame.mixer.Channel(LIVE_POOL + LIBRARY_CHANNELS), options=LONG_CHUNK)
        voice.stream.start()
        held = weakref.ref(voice.stream.held_chunks[0])
        pygame.mixer.stop()
        stop_mixer()
        pygame.mixer.init(frequency=RATE, size=-16, channels=2, buffer=512)

        del voice
        gc.collect()

        assert held() is None
        assert unraisable == []
        assert len(live.take_unreleased_live_stream_reports()) == 1

    def test_the_registry_finds_a_stream_holding_chunks_even_once_its_dict_exists(self, mocker):
        """Exact enumeration: patching a stream (which makes its ``__dict__``) hides nothing."""
        voice = _voice(pygame.mixer.Channel(0), options=LONG_CHUNK)
        voice.stream.start()
        voice.stream.update()
        mocker.patch.object(voice.stream, 'pause')

        holding = live.live_streams_holding_chunks()

        assert any(stream is voice.stream for stream in holding)
        del holding
        voice.stream.stop_now()
        assert live.live_streams_holding_chunks() == ()

    def test_a_finalizers_report_reaches_the_registry_whatever_the_logger_levels(self, caplog):
        """A test's logger levels cannot hide a missing release: the report is not a log record."""
        caplog.set_level(logging.ERROR, logger='game')
        voice = _voice(pygame.mixer.Channel(0), options=LONG_CHUNK)
        voice.stream.start()

        del voice
        gc.collect()

        reports = live.take_unreleased_live_stream_reports()
        assert [(report.stream_name, report.held_chunk_count) for report in reports] == [
            ('str on channel 0', 1)
        ]
        assert live.take_unreleased_live_stream_reports() == ()

    def test_a_voice_stopped_before_it_is_dropped_reports_nothing(self, monkeypatch):
        """A released voice holds no chunk, so its finalizer has nothing to report."""
        unraisable = []
        monkeypatch.setattr(sys, 'unraisablehook', unraisable.append)
        voice = _voice(pygame.mixer.Channel(0), options=LONG_CHUNK)
        voice.stream.start()
        voice.stream.update()
        voice.stream.stop_now()

        del voice
        gc.collect()

        assert unraisable == []
        assert live.take_unreleased_live_stream_reports() == ()

    def test_a_voice_on_a_channel_past_a_shrunk_pool_is_silent(self, mocker):
        """A stale stream past ``get_num_channels()`` never reaches pygame's ``chan_play``.

        pygame indexes its table with SDL's -1 when SDL refuses the channel: a write before the
        table. The stream renders nothing and plays nothing there.
        """
        stale_index = pygame.mixer.get_num_channels() - 1
        playing = _voice(pygame.mixer.Channel(stale_index), options=LONG_CHUNK).stream
        playing.start()
        never_started = _voice(pygame.mixer.Channel(stale_index), options=LONG_CHUNK).stream
        rendered = mocker.patch.object(playing, '_next_chunk', wraps=playing._next_chunk)
        rendered_unstarted = mocker.patch.object(
            never_started, '_next_chunk', wraps=never_started._next_chunk
        )
        pygame.mixer.set_num_channels(stale_index)  # stops the shrunk-off channel: an underrun

        playing.update()
        never_started.start()

        rendered.assert_not_called()
        rendered_unstarted.assert_not_called()
        assert playing.held_chunks == ()
        assert never_started.held_chunks == ()


class TestChunksTheChannelNames:
    """Which Sounds a channel names, read only where pygame's unchecked table has the channel.

    Only ``live.py`` stores ``Channel`` objects, so only its reads can outlive a mixer quit or
    restart: a fresh ``pygame.mixer.Channel(index)`` checks init and range itself.
    """

    @staticmethod
    def _channel_that_must_not_be_read(mocker, *, index):
        """A channel whose table reads fail the test: pygame would read outside its table.

        Returns:
            The channel.
        """
        unread = AssertionError("read outside pygame's channel table")
        return mocker.Mock(
            id=index,
            get_sound=mocker.Mock(side_effect=unread),
            get_queue=mocker.Mock(side_effect=unread),
        )

    def test_a_quit_mixer_names_nothing_and_its_table_is_not_read(self, mocker):
        if pygame.mixer.get_init() is not None:
            stop_mixer()
        channel = self._channel_that_must_not_be_read(mocker, index=0)

        assert live._channel_table_slots(channel) == (None, None)

    def test_a_channel_past_a_restarted_mixers_table_names_nothing_and_is_not_read(self, mocker):
        start_reserved_mixer()
        try:
            pygame.mixer.set_reserved(0)
            pygame.mixer.quit()
            pygame.mixer.init(frequency=RATE, size=-16, channels=2, buffer=512)
            channel = self._channel_that_must_not_be_read(
                mocker, index=pygame.mixer.get_num_channels()
            )

            assert live._channel_table_slots(channel) == (None, None)
        finally:
            stop_mixer()

    def test_a_channel_inside_the_table_names_what_plays_and_what_is_queued(self):
        start_reserved_mixer()
        try:
            channel = pygame.mixer.Channel(0)
            stream = _voice(channel, options=LONG_CHUNK).stream
            stream.start()
            stream.update()

            assert live._channel_table_slots(channel) == stream.held_chunks
            stream.stop_now()
            assert live._channel_table_slots(channel) == (None, None)
        finally:
            stop_mixer()

    def test_an_update_never_reads_the_table_past_its_end(self, mocker):
        """A busy-looking channel past the table: update asks pygame's table nothing."""
        channel = self._channel_that_must_not_be_read(mocker, index=pygame.mixer.get_num_channels())
        channel.get_busy.return_value = True
        stream = _voice(channel, options=LONG_CHUNK).stream
        stream._state = VoiceState.PLAYING  # started before the pool shrank

        stream.update()

        channel.queue.assert_not_called()
        channel.play.assert_not_called()


# Loud enough to clip: a chunk at its gains must hold whatever the samples are
CLIPPING_LEVEL = 2.0
FULL_SCALE = 32767
# A straight ramp across the whole swing is 3 dB down half way; a chunk's loudest is never less
MINIMUM_RAMP_LOUDNESS = 0.7
MIXER_VOLUME_STEPS = 128


class HeldChannel:
    """A real channel that never plays on its own: paused whenever a chunk starts on it.

    What is on the channel then changes only when the test says so (``stop`` starts the queued
    chunk), however long the machine stalls between two lines of a test.
    """

    def __init__(self, index):
        """Hold a mixer channel."""
        self._channel = pygame.mixer.Channel(index)

    def __getattr__(self, name):
        """Everything else is the channel's own.

        Returns:
            The channel's attribute.
        """
        return getattr(self._channel, name)

    def play(self, sound):
        """Play a chunk, paused at once."""
        self._channel.play(sound)
        self._channel.pause()

    def stop(self):
        """Stop the chunk; the queued one starts, paused at once."""
        self._channel.stop()
        self._channel.pause()

    def unpause(self):
        """Stay paused: a resumed stream still plays only when the test says so."""


def _constant_stream(*, level=0.5, chunk_seconds=0.5, **options):
    """A stream of constant samples on channel 0, held: each chunk's level is its gain.

    Returns:
        The stream.
    """
    return LiveStream(
        channel=HeldChannel(0),
        owner='scene',
        render=lambda count: np.full(count, level),
        sample_rate=RATE,
        options=LiveVoiceOptions(chunk_seconds=chunk_seconds, **options),
    )


def _frames(sound):
    """A chunk's frames as heard: its samples at its volume, -1 to 1.

    Returns:
        (count, 2) on a stereo mixer, (count,) on a mono one.
    """
    return pygame.sndarray.array(sound) / FULL_SCALE * sound.get_volume()


def _played_out(stream, *, chunk_count):
    """Start a stream and play it out chunk by chunk.

    ``Channel.stop()`` starts the queued chunk (the module's channel facts).

    Returns:
        Each chunk's frames, in the order they play.
    """
    stream.start()
    chunks = []
    for _ in range(chunk_count):
        chunks.append(_frames(stream.channel.get_sound()))
        stream.update()
        stream.channel.stop()
    stream.stop_now()
    return chunks


class TestLiveStreamGains:
    """A live sound's gains are in its chunks, every one, and no chunk is louder than them.

    SDL_mixer drops a channel's pan when a queued chunk starts
    (bugs/2026-11-25-live-sounds-lose-their-pan.md), so nothing may depend on the channel's.
    Real mixer on the dummy driver: what a chunk holds is what is heard, on a channel at full.
    """

    @pytest.fixture(autouse=True)
    def mixer(self):
        """A stereo mixer on the dummy driver, stopped after.

        Yields:
            None.
        """
        start_mixer(channels=2)
        yield
        pygame.mixer.stop()
        stop_mixer()

    @pytest.mark.parametrize('pan', [-1.0, -0.25, 0.0, 0.5, 1.0])
    def test_every_chunk_is_at_its_gains_from_its_first_sample_to_its_last(self, pan):
        """One law for every sound, live and baked: centre is 3 dB down on each side."""
        gains = constant_power_gains(pan=pan, gain=0.5)

        for chunk in _played_out(_constant_stream(pan=pan), chunk_count=4):
            np.testing.assert_allclose(chunk, np.tile(gains, (len(chunk), 1)), atol=1e-4)

    def test_a_pan_set_before_the_start_is_the_first_chunks_from_its_first_sample(self):
        stream = _constant_stream()
        stream.set_pan(1.0)

        (chunk,) = _played_out(stream, chunk_count=1)

        np.testing.assert_allclose(chunk, np.tile([0.0, 0.5], (len(chunk), 1)), atol=1e-4)

    def test_a_pan_change_ramps_across_the_chunk_already_queued(self):
        """Heard within one chunk, no step: from where the chunk playing ends to the new pan."""
        stream = _constant_stream(pan=-1.0)
        stream.start()
        stream.update()
        playing, queued = stream.channel.get_sound(), stream.channel.get_queue()
        before = _frames(playing)

        stream.set_pan(0.0)  # superseded before it is heard: it leaves no trace
        stream.set_pan(1.0)

        assert stream.channel.get_queue() is queued
        np.testing.assert_array_equal(_frames(playing), before)
        ramped = _frames(queued)
        heard = np.concatenate([before, ramped])
        largest_step = np.abs(np.diff(heard, axis=0)).max()
        assert largest_step <= 0.5 / stream.chunk_samples + 2 / FULL_SCALE
        np.testing.assert_allclose(ramped[-1], [0.0, 0.5], atol=1e-4)
        stream.channel.stop()
        stream.update()
        following = _frames(stream.channel.get_queue())
        np.testing.assert_allclose(following, np.tile([0.0, 0.5], (len(following), 1)), atol=1e-4)
        stream.stop_now()

    def test_a_chunk_that_starts_while_its_rewrite_is_made_is_left_as_it_was(self, mocker):
        """Rewriting what plays would step: the next chunk ramps instead, from what is heard."""
        stream = _constant_stream(pan=-1.0)
        stream.start()
        stream.update()
        queued = stream.channel.get_queue()
        before = _frames(queued)
        real = live.panned_pcm16

        def promoted_meanwhile(*arguments, **settings):
            stream.channel.stop()  # the queued chunk starts
            return real(*arguments, **settings)

        patched = mocker.patch.object(live, 'panned_pcm16', side_effect=promoted_meanwhile)
        stream.set_pan(1.0)
        mocker.stop(patched)
        stream.update()

        assert stream.channel.get_sound() is queued
        np.testing.assert_array_equal(_frames(queued), before)
        following = _frames(stream.channel.get_queue())
        np.testing.assert_allclose(following[0], [0.5, 0.0], atol=1e-3)
        np.testing.assert_allclose(following[-1], [0.0, 0.5], atol=1e-4)
        stream.stop_now()

    def test_a_pan_set_to_what_it_is_rewrites_nothing(self, mocker):
        stream = _constant_stream(pan=-1.0)
        stream.start()
        stream.update()
        rewrite = mocker.patch.object(live, 'panned_pcm16')

        stream.set_pan(-1.0)

        rewrite.assert_not_called()
        stream.stop_now()

    def test_a_pan_change_with_nothing_queued_ramps_across_the_next_chunk(self):
        stream = _constant_stream(pan=-1.0)
        stream.start()

        stream.set_pan(1.0)
        stream.update()

        ramped = _frames(stream.channel.get_queue())
        np.testing.assert_allclose(ramped[0], [0.5, 0.0], atol=2e-3)
        np.testing.assert_allclose(ramped[-1], [0.0, 0.5], atol=1e-4)
        stream.stop_now()

    def test_a_paused_sounds_pan_change_is_in_its_queued_chunk_when_it_resumes(self):
        stream = _constant_stream(pan=-1.0)
        stream.start()
        stream.update()
        stream.pause()

        stream.set_pan(1.0)
        stream.resume()

        assert stream.state is VoiceState.PLAYING
        np.testing.assert_allclose(_frames(stream.channel.get_queue())[-1], [0.0, 0.5], atol=1e-4)
        stream.stop_now()

    def test_a_pan_change_keeps_the_queued_chunks_stopping_fade(self):
        stream = _constant_stream(pan=-1.0)
        stream.start()
        stream.stop(fade_out=0.5)
        stream.update()

        stream.set_pan(0.0)

        faded = _frames(stream.channel.get_queue())
        middle = len(faded) // 2
        # Half way through a straight fade and a straight ramp from (1, 0) to (0.707, 0.707)
        expected = 0.5 * 0.5 * np.array([(1.0 + np.sqrt(0.5)) / 2.0, np.sqrt(0.5) / 2.0])
        np.testing.assert_allclose(faded[middle], expected, atol=1e-3)
        np.testing.assert_allclose(faded[-1], [0.0, 0.0], atol=1e-4)
        stream.stop_now()

    def test_a_ducked_buss_chunks_are_at_its_gain_and_the_pan_changed_or_not(self):
        stream = _constant_stream(pan=-1.0, gain_source=lambda: 0.25)
        stream.start()
        stream.update()
        np.testing.assert_allclose(_frames(stream.channel.get_sound())[-1], [0.125, 0.0], atol=1e-4)

        stream.set_pan(1.0)

        np.testing.assert_allclose(_frames(stream.channel.get_queue())[-1], [0.0, 0.125], atol=1e-4)
        stream.stop_now()

    def test_a_pan_change_never_unmutes_an_inner_game_gone_silent(self):
        """Going silent mutes the chunks under way; a pan change rewrites one, still muted."""
        start_reserved_mixer()
        reserve_inner_game_channels(games=1)
        tile = EngineContext(name='tile')
        with tile.active():
            block = inner_context_partition(live_pool=4, library_channels=32)
            audio = LiveAudio(channel_indices=block.live)
            stream = audio.create_instrument_voice(
                owner='scene', instrument=SINE, frequency=220.0, options=LONG_CHUNK
            ).stream
            stream._channel = HeldChannel(block.live[0])
            stream.start()
            stream.update()
            queued = stream.channel.get_queue()
            heard = _frames(queued)
            set_audible(audible=False)

            stream.set_pan(1.0)

        assert np.abs(heard).max() > 0.5
        assert queued.get_volume() == 0.0
        assert pygame.sndarray.array(queued)[-1, 0] == 0  # rewritten, though unheard
        stream.stop_now()

    def test_a_pan_change_draws_no_noise_and_leaves_the_next_chunk_as_it_was(self):
        """The rewrite renders nothing: the noise a pan change finds is the noise after it."""
        noise = Instrument(noise='white', live=True)
        mono = []
        for pans in ((), (-1.0, 0.5)):
            stream = _voice(
                HeldChannel(0),
                instrument=noise,
                random_source=np.random.default_rng(5),
                options=LONG_CHUNK,
            ).stream
            stream.start()
            stream.update()
            for pan in pans:
                stream.set_pan(pan)
            mono.append(stream._render(stream.chunk_samples))
            stream.stop_now()

        np.testing.assert_array_equal(mono[0], mono[1])

    def test_a_stopped_streams_pan_change_leaves_another_voices_chunk_alone(self):
        stopped = _constant_stream(pan=-1.0)
        stopped.start()
        stopped.stop_now()
        other = _constant_stream(pan=0.0)
        other.start()
        other.update()
        before = _frames(other.channel.get_queue())

        stopped.set_pan(1.0)

        np.testing.assert_array_equal(_frames(other.channel.get_queue()), before)
        other.stop_now()

    def test_an_overtaken_streams_pan_change_leaves_the_chunk_queued_over_its_own_alone(self):
        overtaken = _constant_stream(pan=-1.0)
        overtaken.start()
        other = _constant_stream(pan=0.0)
        other.start()
        other.update()
        before = _frames(other.channel.get_queue())

        overtaken.set_pan(1.0)

        np.testing.assert_array_equal(_frames(other.channel.get_queue()), before)
        other.stop_now()
        overtaken.stop_now()

    def test_no_chunk_is_ever_louder_than_its_voices_gains(self):
        """The invariant: whatever is done to a sound, its power stays within its gain's.

        Constant power: left squared plus right squared is the gain squared, and a ramp between
        two pans stays inside that circle. The samples clip, so nothing hides behind them.
        """
        chooser = np.random.default_rng(LIVE_STREAM_TEST_SEED)
        gain = 1.0
        stream = _constant_stream(level=CLIPPING_LEVEL, gain_source=lambda: gain)
        stream.start()
        rendered = [(stream.channel.get_sound(), gain)]  # each chunk, the gain it was rendered at
        for _ in range(60):
            action = chooser.integers(5)
            if action == 0:
                stream.set_pan(float(chooser.uniform(-1.0, 1.0)))
            elif action == 1:
                stream.pause()
                stream.resume()
            elif action == 2:
                stream.channel.stop()  # the queued chunk starts
            elif action == 3:
                stream.channel.stop()
                stream.channel.stop()  # idle: the next update restarts
            else:
                gain = float(chooser.uniform(0.0, 1.0))
            stream.update()
            for chunk in _channel_slots(stream.channel):
                if not any(chunk is known for known, _ in rendered):
                    rendered.append((chunk, gain))
            for chunk, gain_in_force in rendered:
                loudness = np.sqrt(np.square(_frames(chunk)).sum(axis=1)).max()
                assert loudness <= gain_in_force + 1e-4
                assert loudness >= gain_in_force * MINIMUM_RAMP_LOUDNESS - 2.0 / MIXER_VOLUME_STEPS
        assert len(rendered) > 20
        assert stream.state is VoiceState.PLAYING
        stream.stop_now()

    @pytest.mark.parametrize('pan', [-1.0, 0.0, 1.0])
    def test_a_mono_mixer_plays_every_chunk_at_the_centre_gain_wherever_it_is_panned(self, pan):
        """A mono mixer has no sides: both sides' mean power, the centred gain, pan or no pan."""
        start_mixer(channels=1)
        centre, _ = constant_power_gains(pan=0.0, gain=0.5)

        for chunk in _played_out(_constant_stream(pan=pan), chunk_count=3):
            np.testing.assert_allclose(chunk, np.full(len(chunk), centre), atol=1e-4)

    def test_a_pan_change_on_a_mono_mixer_ends_at_the_same_gain(self):
        start_mixer(channels=1)
        centre, _ = constant_power_gains(pan=0.0, gain=0.5)
        stream = _constant_stream(pan=-1.0)
        stream.start()
        stream.update()

        stream.set_pan(1.0)

        assert _frames(stream.channel.get_queue())[-1] == pytest.approx(centre, abs=1e-4)
        stream.stop_now()


class TestHeardPans:
    """What the mixer plays, recorded on SDL's disk driver (tests/audio/live_pan_probe.py).

    The channel's own gains show nowhere else. Only levels are asserted, never times.
    """

    LEVEL = live_pan_probe.LEVEL
    TOLERANCE = 0.001

    @pytest.fixture
    def heard(self, tmp_path):
        """Record a case.

        Returns:
            A function from a case to its sounding frames, (count, 2), -1 to 1.
        """

        def record(case):
            path = tmp_path / f'{case}.raw'
            result = run_command(
                command=[sys.executable, '-m', live_pan_probe.__name__, case],
                environment={
                    **os.environ,
                    'SDL_AUDIODRIVER': 'disk',
                    'SDL_DISKAUDIOFILE': str(path),
                    'SDL_VIDEODRIVER': 'dummy',
                },
                timeout_seconds=RECORDING_TIMEOUT_SECONDS,
                capture_output=OutputCapture.TOGETHER,
                working_directory=REPOSITORY_ROOT,
            )
            assert result.returncode == 0, result.stdout
            raw = np.fromfile(path, dtype='<i2')
            frames = raw[: raw.size - raw.size % 2].reshape(-1, 2) / FULL_SCALE
            sounding = frames[np.abs(frames).max(axis=1) > 0.0]
            # More than the chunk playing and the one queued: later chunks are heard too
            assert len(sounding) > 2 * live_pan_probe.CHUNK_SECONDS * RATE
            return sounding

        return record

    @pytest.mark.parametrize(
        'case',
        [
            live_pan_probe.LEFT,
            live_pan_probe.RESTARTED,
            live_pan_probe.PAUSED,
            live_pan_probe.RELEASED,
        ],
    )
    def test_a_sound_on_the_left_is_never_heard_on_the_right(self, heard, case):
        frames = heard(case)

        assert np.abs(frames[:, 1]).max() == 0.0
        assert frames[:, 0].max() == pytest.approx(self.LEVEL, abs=self.TOLERANCE)

    def test_a_centred_sound_on_a_channel_left_panned_is_at_the_centre_gain_throughout(self, heard):
        frames = heard(live_pan_probe.CENTRE_ON_A_PANNED_CHANNEL)

        centre, _ = constant_power_gains(pan=0.0, gain=self.LEVEL)
        np.testing.assert_allclose(frames, np.full_like(frames, centre), atol=self.TOLERANCE)

    def test_a_stealer_is_heard_on_its_own_side_and_the_stolen_on_its_own(self, heard):
        frames = heard(live_pan_probe.STOLEN)

        assert np.minimum(np.abs(frames[:, 0]), np.abs(frames[:, 1])).max() == 0.0
        assert frames[0, 0] == pytest.approx(self.LEVEL, abs=self.TOLERANCE)
        assert frames[-1, 1] == pytest.approx(self.LEVEL, abs=self.TOLERANCE)

    def test_a_sound_moved_to_the_right_ends_there_and_is_never_louder_than_its_gains(self, heard):
        frames = heard(live_pan_probe.MOVED)

        assert np.sqrt(np.square(frames).sum(axis=1)).max() <= self.LEVEL + self.TOLERANCE
        np.testing.assert_allclose(frames[0], self.LEVEL * np.sqrt(0.5), atol=self.TOLERANCE)
        np.testing.assert_allclose(frames[-1], [0.0, self.LEVEL], atol=self.TOLERANCE)

    def test_the_channels_next_user_inherits_no_pan(self, heard):
        """A guard, not a regression's proof: the mixer dropped the pan before the fix too."""
        frames = heard(live_pan_probe.NEXT_USER)

        np.testing.assert_allclose(frames[-1], live_pan_probe.NEXT_USER_LEVEL, atol=self.TOLERANCE)
