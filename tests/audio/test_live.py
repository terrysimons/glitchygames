"""Tests for real-time synth voices."""

import numpy as np
import pytest

from glitchygames.audio import live
from glitchygames.audio.live import LiveAudio, LiveVoice, VoiceState, reserve_live_voice_pool
from glitchygames.audio.recipes import Tremolo
from glitchygames.audio.synth import Waveform
from glitchygames.randomness import numpy_stream, reset_streams

RATE = 44100
LIVE_STREAM_TEST_SEED = 78


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
        'waveform': Waveform.SINE,
        'frequency': 220.0,
        'volume': 0.5,
        'sample_rate': RATE,
        'random_source': np.random.default_rng(5),
    }
    settings.update(overrides)
    return LiveVoice(**settings)


class TestPoolReservation:
    """Mixer channel pool reservation."""

    def test_grows_mixer_and_reserves_low_channels(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=(RATE, -16, 2))
        mocker.patch('pygame.mixer.get_num_channels', return_value=8)
        set_num = mocker.patch('pygame.mixer.set_num_channels')
        mocker.patch('pygame.mixer.set_reserved', side_effect=lambda count: count)
        assert reserve_live_voice_pool(4) == (0, 1, 2, 3)
        set_num.assert_called_once_with(12)

    def test_zero_pool_or_no_mixer_reserves_nothing(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=None)
        assert reserve_live_voice_pool(4) == ()

    def test_negative_pool_raises(self):
        with pytest.raises(ValueError, match='pool_size'):
            reserve_live_voice_pool(-1)


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
        voice = _voice(channel)
        voice.start()
        channel.play.assert_called_once()
        voice.update()
        channel.queue.assert_called_once()
        assert len(rendered_chunks[0]) == 4410  # 100 ms at 44100 Hz

    def test_update_waits_while_queue_full(self, channel, rendered_chunks):
        voice = _voice(channel)
        voice.start()
        channel.get_queue.return_value = object()
        voice.update()
        channel.queue.assert_not_called()

    def test_phase_continuous_across_chunks(self, channel, rendered_chunks):
        voice = _voice(channel, volume=1.0)
        voice.start()
        voice.update()
        joined = np.concatenate(rendered_chunks)
        expected = np.sin(2 * np.pi * 220.0 * np.arange(len(joined)) / RATE)
        np.testing.assert_allclose(joined, expected, atol=1e-9)

    def test_frequency_change_ramps_over_one_chunk(self, channel, rendered_chunks):
        voice = _voice(channel, volume=1.0)  # SINE: a sawtooth reset could land on the boundary
        voice.start()
        voice.frequency = 440.0
        voice.update()
        second = rendered_chunks[1]
        # No discontinuity at the boundary: first sample of chunk 2 continues chunk 1
        assert abs(second[0] - rendered_chunks[0][-1]) < 0.1

    def test_volume_change_ramps(self, channel, rendered_chunks):
        voice = _voice(channel, volume=0.0)
        voice.start()
        voice.volume = 1.0
        voice.update()
        envelope = np.abs(rendered_chunks[1])
        assert envelope[:100].max() < 0.05
        assert envelope[-200:].max() > 0.9

    def test_filter_and_tremolo_continue_across_chunks(self, channel, rendered_chunks):
        # 177 Hz: the low-pass delays each sawtooth reset by about 50 samples, and at this pitch
        # the delayed resets fall ~125 samples either side of the chunk boundary (233 Hz put
        # one exactly on it, which is a real waveform edge, not a continuity bug)
        voice = _voice(
            channel,
            volume=1.0,
            waveform=Waveform.SAWTOOTH,
            frequency=177.0,
            low_pass_cutoff=800.0,
            tremolo=Tremolo(rate_hz=7.0, depth=0.5),
        )
        voice.start()
        voice.update()
        boundary_step = abs(rendered_chunks[1][0] - rendered_chunks[0][-1])
        typical_step = np.median(np.abs(np.diff(rendered_chunks[0])))
        assert boundary_step < typical_step * 4

    def test_cutoff_change_crossfades(self, channel, rendered_chunks):
        voice = _voice(
            channel,
            volume=1.0,
            waveform=Waveform.SAWTOOTH,
            frequency=233.0,
            low_pass_cutoff=4000.0,
        )
        voice.start()
        voice.low_pass_cutoff = 300.0
        voice.update()
        assert abs(rendered_chunks[1][0] - rendered_chunks[0][-1]) < 0.2


class TestLiveVoiceStopping:
    """Stopping, pausing and underrun recovery."""

    def test_stop_fades_then_drains_without_channel_stop(self, channel, rendered_chunks):
        voice = _voice(channel, volume=1.0)
        voice.start()
        voice.stop(fade_out=0.1)
        voice.update()
        assert abs(rendered_chunks[-1][-1]) < 1e-9  # Faded to silence
        assert voice.state is VoiceState.DRAINING
        voice.update()
        assert channel.queue.call_count == 1  # No more chunks after the fade
        channel.stop.assert_not_called()  # stop()/fadeout() would start the queued chunk
        assert voice.is_playing
        channel.get_busy.return_value = False
        assert not voice.is_playing

    def test_stop_now_silences_immediately(self, channel, rendered_chunks):
        voice = _voice(channel)
        voice.start()
        voice.stop_now()
        assert channel.stop.call_count == 2  # First starts the queued chunk, second stops it
        assert voice.state is VoiceState.STOPPED

    def test_setters_on_stopped_voice_are_ignored(self, channel, rendered_chunks):
        voice = _voice(channel)
        voice.start()
        voice.stop_now()
        voice.frequency = 999.0
        voice.update()
        assert len(rendered_chunks) == 1

    def test_underrun_recovers(self, channel, rendered_chunks, mocker):
        """Review focus 5: a long hitch drains the channel; the voice restarts."""
        debug = mocker.patch.object(live.log, 'debug')
        voice = _voice(channel)
        voice.start()
        channel.get_busy.return_value = False
        voice.update()
        assert debug.called
        assert channel.queue.call_count + channel.play.call_count >= 2

    def test_pause_and_resume(self, channel, rendered_chunks):
        voice = _voice(channel)
        voice.start()
        voice.pause()
        channel.pause.assert_called_once()
        voice.update()
        channel.queue.assert_not_called()
        voice.resume()
        channel.unpause.assert_called_once()

    def test_silent_voice_without_channel(self, rendered_chunks):
        voice = _voice(None)
        voice.start()
        voice.update()
        voice.stop_now()
        assert not voice.is_playing
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
                get_queue=mocker.Mock(return_value=None),
                get_busy=mocker.Mock(return_value=True),
            ),
        )
        return LiveAudio(channel_indices=(0, 1))

    def _create(self, audio, owner):
        return audio.create_voice(owner=owner, waveform=Waveform.SINE, frequency=100.0)

    def test_pool_exhaustion_raises_at_limit_plus_one(self, audio):
        self._create(audio, 'scene')
        self._create(audio, 'scene')
        with pytest.raises(ValueError, match='live-voice-pool'):
            self._create(audio, 'scene')

    def test_playing_voice_count(self, audio):
        """playing_voice_count counts only voices that are currently playing."""
        first = self._create(audio, 'scene')
        self._create(audio, 'scene')
        assert audio.playing_voice_count == 0
        first.start()
        assert audio.playing_voice_count == 1

    def test_released_channels_are_reused(self, audio):
        first = self._create(audio, 'scene')
        self._create(audio, 'scene')
        audio.release_voice(first)
        assert self._create(audio, 'scene') is not None

    def test_owner_rules(self, audio):
        active = self._create(audio, 'active')
        paused = self._create(audio, 'previous')
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
        voice = self._create(audio, transition)
        voice.start()
        audio.update(active_scene='new', previous_scene='old', active_transitions=(transition,))
        assert voice.state is VoiceState.PLAYING
        audio.update(active_scene='new', previous_scene='old', active_transitions=(None,))
        assert voice.state is VoiceState.STOPPED

    def test_fading_voice_finishes_when_owner_becomes_previous_scene(self, audio, rendered_chunks):
        voice = self._create(audio, 'scene')
        voice.start()
        voice.stop(fade_out=0.1)
        audio.update(active_scene='pause', previous_scene='scene', active_transitions=())
        assert abs(rendered_chunks[-1][-1]) < 1e-9  # The fade chunk was queued
        assert voice.state is VoiceState.DRAINING

    def test_paused_voice_that_is_stopped_renders_its_fade(self, audio, rendered_chunks):
        voice = self._create(audio, 'scene')
        voice.start()
        audio.update(active_scene='pause', previous_scene='scene', active_transitions=())
        assert voice.state is VoiceState.PAUSED
        voice.stop(fade_out=0.1)
        audio.update(active_scene='pause', previous_scene='scene', active_transitions=())
        assert abs(rendered_chunks[-1][-1]) < 1e-9
        assert voice.state is VoiceState.DRAINING

    def test_stopped_voice_returns_its_channel_to_the_pool(self, mocker, rendered_chunks):
        mocker.patch('pygame.mixer.get_init', return_value=(RATE, -16, 2))
        mocker.patch('pygame.mixer.Channel', side_effect=lambda index: mocker.Mock())
        single = LiveAudio(channel_indices=(0,))
        voice = self._create(single, 'scene')
        voice.start()
        voice.stop_now()
        single.update(active_scene='scene', previous_scene=None, active_transitions=())
        assert self._create(single, 'scene') is not None

    def test_drained_voice_returns_its_channel_to_the_pool(self, mocker, rendered_chunks):
        mocker.patch('pygame.mixer.get_init', return_value=(RATE, -16, 2))
        drained_channel = mocker.Mock()
        drained_channel.get_queue.return_value = None
        drained_channel.get_busy.return_value = True
        mocker.patch('pygame.mixer.Channel', return_value=drained_channel)
        single = LiveAudio(channel_indices=(0,))
        voice = self._create(single, 'scene')
        voice.start()
        voice.stop(fade_out=0.1)
        single.update(active_scene='scene', previous_scene=None, active_transitions=())
        assert voice.state is VoiceState.DRAINING
        drained_channel.get_busy.return_value = False
        single.update(active_scene='scene', previous_scene=None, active_transitions=())
        assert self._create(single, 'scene') is not None

    def test_releasing_a_voice_twice_is_idempotent(self, audio):
        first = self._create(audio, 'scene')
        audio.release_voice(first)
        audio.release_voice(first)
        self._create(audio, 'scene')
        self._create(audio, 'scene')
        with pytest.raises(ValueError, match='live-voice-pool'):
            self._create(audio, 'scene')

    def test_no_mixer_returns_silent_voice(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=None)
        voice = LiveAudio(channel_indices=()).create_voice(
            owner='scene', waveform=Waveform.SINE, frequency=100.0
        )
        voice.start()
        assert not voice.is_playing
