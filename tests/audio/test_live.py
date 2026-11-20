"""Tests for live voices' channel and lifecycle (LiveStream) and the live pool (LiveAudio).

Every live voice is a live instrument's (``live_instrument.InstrumentVoice``); its rendering is
tested in tests/audio/test_live_instrument.py. Here a plain live sine plays through the stream:
start, one chunk queued, fades, pause, underruns, the pool's owner rules, live pools per
engine context.
"""

import numpy as np
import pygame
import pytest

from glitchygames.audio import live
from glitchygames.audio.effects import Tremolo
from glitchygames.audio.instrument import Filter, Instrument
from glitchygames.audio.live import LiveAudio, LiveVoiceOptions, VoiceState
from glitchygames.audio.live_instrument import InstrumentVoice
from glitchygames.audio.route import set_audible
from glitchygames.audio.voices import inner_context_partition, reserve_inner_game_channels
from glitchygames.engine_context import EngineContext
from glitchygames.randomness import numpy_stream, reset_streams
from tests.audio.library_support import stop_mixer
from tests.audio.voice_support import start_reserved_mixer

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

    def fake_to_sound(samples, *, volume):
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
    mocked_channel = mocker.Mock()
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

        def fake_to_sound(samples, *, volume):
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

    def test_every_voice_pans_its_channel_by_the_constant_power_law_centre_by_default(
        self, channel, rendered_chunks
    ):
        """One law for every sound, live and baked: centre is 3 dB down on each side."""
        from glitchygames.audio.voices import constant_power_gains

        centred = _voice(channel).stream
        centred.start()
        channel.set_volume.assert_called_with(*constant_power_gains(pan=0.0, gain=1.0))

        panned = _voice(channel, options=LiveVoiceOptions(pan=0.5)).stream
        panned.start()
        channel.set_volume.assert_called_with(*constant_power_gains(pan=0.5, gain=1.0))

        panned.set_pan(-0.25)
        channel.set_volume.assert_called_with(*constant_power_gains(pan=-0.25, gain=1.0))

    def test_a_voice_never_inherits_the_pan_its_channel_had(self, channel, rendered_chunks):
        """Each voice sets its channel's pan as it starts: the pool's channels are reused."""
        from glitchygames.audio.voices import constant_power_gains

        hard_left = _voice(channel, options=LiveVoiceOptions(pan=-1.0)).stream
        hard_left.start()
        hard_left.stop_now()

        _voice(channel).stream.start()

        channel.set_volume.assert_called_with(*constant_power_gains(pan=0.0, gain=1.0))

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
